export const l = 1;
export async function ok(): Promise<Response> {
  return await fetch("/x");
}
