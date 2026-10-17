"use client";

import { Component, type ReactNode } from "react";

/** A failed decorative effect must leave the page and navigation usable. */
export class VisualEffectBoundary extends Component<
  { children: ReactNode; fallback?: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() { return { failed: true }; }

  render() {
    return this.state.failed ? this.props.fallback ?? null : this.props.children;
  }
}
