export function localDateTimeToIso(value: string): string {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) {
    throw new Error("Choose a valid transaction date and time.");
  }
  return date.toISOString();
}

export function isoToLocalDateTime(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function formatTransactionAmount(amount: string, currency: string, locale: "ru" | "uk") {
  const negative = amount.startsWith("-");
  const unsigned = negative ? amount.slice(1) : amount;
  const [integerPart, fractionPart = ""] = unsigned.split(".");
  const integer = BigInt(integerPart || "0");
  const localeName = locale === "uk" ? "uk-UA" : "ru-UA";
  const whole = new Intl.NumberFormat(localeName, {
    maximumFractionDigits: 0,
    useGrouping: true,
  }).format(integer);
  const fraction = `${fractionPart}00`.slice(0, 2);
  const pattern = new Intl.NumberFormat(localeName, {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).formatToParts(negative ? -1 : 1);
  let inserted = false;
  return pattern.map((part) => {
    if (["integer", "group", "decimal", "fraction"].includes(part.type)) {
      if (inserted) return "";
      inserted = true;
      const decimal = pattern.find((item) => item.type === "decimal")?.value ?? ".";
      return `${whole}${decimal}${fraction}`;
    }
    return part.value;
  }).join("");
}
