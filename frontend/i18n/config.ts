export const locales = ["vi", "en"] as const;

export type Locale = (typeof locales)[number];

export const defaultLocale: Locale = "vi";

// NEXT_LOCALE là tên cookie quy ước sẵn của next-intl; đặt thành hằng số để đường đọc
// (request config) và đường ghi (server action) không lệch nhau vì một lỗi gõ.
export const LOCALE_COOKIE = "NEXT_LOCALE";

export function isLocale(value: string | undefined): value is Locale {
  return locales.includes(value as Locale);
}
