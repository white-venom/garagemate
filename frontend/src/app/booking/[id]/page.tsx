import type { Metadata } from "next";

import BookingDetails from "@/components/BookingDetails";

export const metadata: Metadata = {
  title: "Your booking - GarageMate",
};

export default async function BookingPage({ params }: PageProps<"/booking/[id]">) {
  const { id } = await params;
  return <BookingDetails id={id} />;
}
