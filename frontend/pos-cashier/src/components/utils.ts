export function formatCLP(value: number): string {
  const rounded = Math.round(value);
  return rounded.toLocaleString('es-CL');
}
