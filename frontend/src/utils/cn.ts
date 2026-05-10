import { clsx, type ClassValue } from "clsx";

/** Tailwind 友好的 classnames 拼接：过滤 falsy + 去重空格。 */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
