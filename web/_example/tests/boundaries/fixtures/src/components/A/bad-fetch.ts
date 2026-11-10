export async function bad(): Promise<Response> {
  return await fetch("/x");
}
