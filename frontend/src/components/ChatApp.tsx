"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError, api, errorMessage } from "@/lib/api";
import type { Attachment, Booking, Conversation, Diagnosis, Message } from "@/lib/types";

import BookingModal from "./BookingModal";
import ChatHeader from "./ChatHeader";
import Composer from "./Composer";
import MessageList from "./MessageList";
import Sidebar from "./Sidebar";
import Toast from "./Toast";

// messages shown in the UI, plus local-only state for ones that haven't reached the server yet
export type ChatItem = Message & {
  localId?: string;
  status?: "sending" | "failed";
  error?: string;
};

const LAST_CONVERSATION_KEY = "garagemate.lastConversation";

function rememberConversation(id: string | null) {
  try {
    if (id) localStorage.setItem(LAST_CONVERSATION_KEY, id);
    else localStorage.removeItem(LAST_CONVERSATION_KEY);
  } catch {
    // storage not available, not a big deal
  }
}

export default function ChatApp() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatItem[]>([]);
  const [loadingConversation, setLoadingConversation] = useState(false);
  const [sending, setSending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [bookingOpen, setBookingOpen] = useState(false);
  const [bookingDiagnosis, setBookingDiagnosis] = useState<Diagnosis | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const localCounter = useRef(0);

  const latestDiagnosis = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].diagnosis) return messages[i].diagnosis;
    }
    return null;
  }, [messages]);

  const upsertConversation = (updated: Conversation) => {
    setConversations((previous) => [updated, ...previous.filter((item) => item.id !== updated.id)]);
  };

  const loadHistory = useCallback(async () => {
    try {
      const data = await api.listConversations();
      setConversations(data.results);
    } catch (error) {
      setToast(errorMessage(error));
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    try {
      const { messages: loaded, ...summary } = await api.getConversation(id);
      setConversation(summary);
      setMessages(loaded);
      rememberConversation(id);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        rememberConversation(null);
        setConversation(null);
        setMessages([]);
      } else {
        setToast(errorMessage(error));
      }
    } finally {
      setLoadingConversation(false);
    }
  }, []);

  // first load: history for the sidebar + reopen whatever chat was open last time
  useEffect(() => {
    let lastId: string | null = null;
    try {
      lastId = localStorage.getItem(LAST_CONVERSATION_KEY);
    } catch {
      lastId = null;
    }
    const tasks: Promise<void>[] = [loadHistory()];
    if (lastId) tasks.push(loadConversation(lastId));
    void Promise.all(tasks);
  }, [loadHistory, loadConversation]);

  const openConversation = (id: string) => {
    setSidebarOpen(false);
    if (id === conversation?.id) return;
    setLoadingConversation(true);
    setMessages([]);
    void loadConversation(id);
  };

  const startNewChat = () => {
    setConversation(null);
    setMessages([]);
    setSidebarOpen(false);
    rememberConversation(null);
  };

  const closeBooking = useCallback(() => setBookingOpen(false), []);
  const dismissToast = useCallback(() => setToast(null), []);

  const openBooking = (diagnosis: Diagnosis | null) => {
    setBookingDiagnosis(diagnosis);
    setBookingOpen(true);
  };

  const send = async (text: string, attachments: Attachment[] = [], retryLocalId?: string) => {
    if (sending) return;
    const localId = retryLocalId ?? `local-${++localCounter.current}`;
    const pendingMessage: ChatItem = {
      id: -Date.now(),
      localId,
      role: "user",
      kind: "text",
      content: text,
      quick_replies: [],
      action: "",
      attachments,
      diagnosis: null,
      booking: null,
      used_ai: false,
      created_at: new Date().toISOString(),
      status: "sending",
    };

    setMessages((previous) =>
      retryLocalId
        ? previous.map((item) => (item.localId === retryLocalId ? pendingMessage : item))
        : [...previous, pendingMessage],
    );
    setSending(true);

    try {
      const response = await api.sendMessage({
        conversation_id: conversation?.id ?? null,
        message: text,
        attachment_ids: attachments.map((attachment) => attachment.id),
      });
      setMessages((previous) => [
        ...previous.filter((item) => item.localId !== localId),
        response.user_message,
        response.reply,
      ]);
      setConversation(response.conversation);
      upsertConversation(response.conversation);
      rememberConversation(response.conversation.id);

      if (response.reply.action === "open_booking") {
        openBooking(response.reply.diagnosis ?? latestDiagnosis);
      }
    } catch (error) {
      setMessages((previous) =>
        previous.map((item) =>
          item.localId === localId ? { ...item, status: "failed", error: errorMessage(error) } : item,
        ),
      );
    } finally {
      setSending(false);
    }
  };

  const retry = (item: ChatItem) => {
    if (item.localId) void send(item.content, item.attachments, item.localId);
  };

  const diagnoseNow = async () => {
    if (!conversation || sending) return;
    setSending(true);
    try {
      const { message } = await api.requestDiagnosis(conversation.id);
      if (message) {
        setMessages((previous) => (previous.some((item) => item.id === message.id) ? previous : [...previous, message]));
      }
      await loadConversation(conversation.id);
      void loadHistory();
    } catch (error) {
      setToast(errorMessage(error));
    } finally {
      setSending(false);
    }
  };

  const deleteConversation = async (id: string) => {
    try {
      await api.deleteConversation(id);
      setConversations((previous) => previous.filter((item) => item.id !== id));
      if (conversation?.id === id) startNewChat();
    } catch (error) {
      setToast(errorMessage(error));
    }
  };

  const handleBooked = (booking: Booking) => {
    // the backend adds a confirmation message to the chat, reload to show it
    if (booking.conversation_id && booking.conversation_id === conversation?.id) {
      void loadConversation(booking.conversation_id);
    }
    void loadHistory();
  };

  return (
    <div className="flex h-dvh overflow-hidden bg-stone-100">
      <Sidebar
        conversations={conversations}
        loading={historyLoading}
        activeId={conversation?.id ?? null}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        onSelect={openConversation}
        onNewChat={startNewChat}
        onDelete={deleteConversation}
      />

      <main className="flex min-w-0 flex-1 flex-col">
        <ChatHeader
          conversation={conversation}
          busy={sending}
          onOpenMenu={() => setSidebarOpen(true)}
          onDiagnose={diagnoseNow}
          onBook={() => openBooking(latestDiagnosis)}
        />

        <MessageList
          messages={messages}
          loading={loadingConversation}
          typing={sending}
          stage={conversation?.stage ?? "new"}
          onQuickReply={(text) => void send(text)}
          onRetry={retry}
          onBook={openBooking}
        />

        <Composer conversationId={conversation?.id ?? null} disabled={sending || loadingConversation} onSend={send} onError={setToast} />
      </main>

      <BookingModal
        open={bookingOpen}
        onClose={closeBooking}
        conversation={conversation}
        diagnosis={bookingDiagnosis ?? latestDiagnosis}
        onBooked={handleBooked}
      />

      <Toast message={toast} onDismiss={dismissToast} />
    </div>
  );
}
