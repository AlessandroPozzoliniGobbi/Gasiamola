"use client";

import { useEffect } from "react";
import { applyUiPreferences, useUiPreferences } from "../../lib/uiPreferences";

/** Applies saved browser preferences to the document on every route. */
export default function ApplyUiPreferences() {
  const { textSize, contrast, reduceMotion, defaultBasemap } = useUiPreferences();
  useEffect(() => {
    applyUiPreferences({ textSize, contrast, reduceMotion, defaultBasemap });
  }, [textSize, contrast, reduceMotion, defaultBasemap]);
  return null;
}
