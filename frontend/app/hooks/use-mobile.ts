import * as React from "react"

const MOBILE_BREAKPOINT = 768
const MOBILE_QUERY = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

function subscribe(onChange: () => void) {
  const mql = window.matchMedia(MOBILE_QUERY)
  mql.addEventListener("change", onChange)
  return () => mql.removeEventListener("change", onChange)
}

// Bản shadcn sinh ra gọi setState ngay trong effect (lint react-hooks/set-state-in-effect
// chặn); useSyncExternalStore đọc media query trực tiếp. Máy chủ luôn coi là màn hình
// rộng, giống giá trị khởi đầu của bản gốc.
export function useIsMobile() {
  return React.useSyncExternalStore(
    subscribe,
    () => window.matchMedia(MOBILE_QUERY).matches,
    () => false
  )
}
