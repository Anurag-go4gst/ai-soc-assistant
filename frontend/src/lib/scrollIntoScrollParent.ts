export function scrollIntoScrollParent(
  element: HTMLElement | null,
  options?: { block?: ScrollLogicalPosition; behavior?: ScrollBehavior },
): void {
  if (!element) return;
  const block = options?.block ?? 'center';
  const behavior = options?.behavior ?? 'smooth';

  let scrollParent: HTMLElement | null = element.parentElement;
  while (scrollParent) {
    const style = window.getComputedStyle(scrollParent);
    const scrollable =
      scrollParent.scrollHeight > scrollParent.clientHeight &&
      (style.overflowY === 'auto' || style.overflowY === 'scroll');
    if (scrollable) break;
    scrollParent = scrollParent.parentElement;
  }

  if (scrollParent && scrollParent !== document.body) {
    const elRect = element.getBoundingClientRect();
    const parentRect = scrollParent.getBoundingClientRect();
    const offset = elRect.top - parentRect.top + scrollParent.scrollTop;
    let top = offset - 12;
    if (block === 'center') {
      top = offset - scrollParent.clientHeight / 2 + element.clientHeight / 2;
    } else if (block === 'end') {
      top = offset - scrollParent.clientHeight + element.clientHeight + 12;
    }
    scrollParent.scrollTo({ top: Math.max(0, top), behavior });
    return;
  }

  if (typeof element.scrollIntoView === 'function') {
    element.scrollIntoView({ behavior, block });
  }
}
