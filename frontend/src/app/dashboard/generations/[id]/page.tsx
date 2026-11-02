import { redirect } from 'next/navigation';
export default async function GenerationPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/dashboard/generations?run=${encodeURIComponent(id)}`);
}
