"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import type { FieldItem } from "../../types/field";
import styles from "../../styles/map.module.css";

type Props = {
  fields: FieldItem[];
  selectedFieldId: string | null;
  onSelectField: (id: string) => void;
  onAnalyzeField: (id: string) => void;
  onAnalyzeAll: () => void;
  onRenameField: (id: string, name: string) => void;
  onDeleteField: (id: string) => void;
  onClearFields: () => void;
  ready: boolean;
};

export default function FieldPanel({
  fields,
  selectedFieldId,
  onSelectField,
  onAnalyzeField,
  onAnalyzeAll,
  onRenameField,
  onDeleteField,
  onClearFields,
  ready,
}: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");

  function beginEditing(field: FieldItem) {
    setEditingId(field.id);
    setDraft(field.name);
  }

  function saveName(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editingId) return;
    onRenameField(editingId, draft);
    setEditingId(null);
  }

  return (
    <section className={styles.fieldPanel}>
      <h2 className={styles.sectionTitle}>Your fields ({fields.length})</h2>
      {fields.length === 0 ? (
        <p className={styles.description}>You have not drawn any fields yet.</p>
      ) : (
        <div className={styles.fieldList}>
          {fields.map((field) => (
            <div className={styles.fieldRow} key={field.id}>
              <span className={styles.fieldNumber}>{field.number}</span>
              {editingId === field.id ? (
                <form className={styles.fieldEditForm} onSubmit={saveName}>
                  <input
                    autoFocus
                    className={styles.fieldEditInput}
                    maxLength={48}
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    aria-label={`New name for field ${field.number}`}
                  />
                  <button type="submit" className={styles.fieldIconButton} aria-label="Save name" title="Save name">✓</button>
                  <button type="button" className={styles.fieldIconButton} onClick={() => setEditingId(null)} aria-label="Cancel renaming" title="Cancel renaming">×</button>
                </form>
              ) : (
                <>
                  <button
                    type="button"
                    className={[styles.fieldSelectButton, selectedFieldId === field.id ? styles.fieldSelectActive : ""].join(" ")}
                    onClick={() => onSelectField(field.id)}
                    aria-pressed={selectedFieldId === field.id}
                    title="Select and zoom to field"
                  >
                    {field.name}
                  </button>
                  <button
                    type="button"
                    className={`${styles.fieldIconButton} ${styles.fieldAnalyzeButton}`}
                    onClick={() => onAnalyzeField(field.id)}
                    disabled={!ready}
                    title={`Analyze ${field.name}`}
                    aria-label={`Analyze ${field.name}`}
                  >
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M4 19h16M7 16v-5M12 16V7M17 16v-8M5 8l5-3 4 2 5-4" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    className={styles.fieldIconButton}
                    onClick={() => beginEditing(field)}
                    disabled={!ready}
                    title={`Rename ${field.name}`}
                    aria-label={`Rename ${field.name}`}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className={[styles.fieldIconButton, styles.fieldDeleteButton].join(" ")}
                    onClick={() => onDeleteField(field.id)}
                    disabled={!ready}
                    title={`Delete ${field.name}`}
                    aria-label={`Delete ${field.name}`}
                  >
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <path d="M3 6h18M8 6V4h8v2M5 6l1 14h12l1-14M10 10v6M14 10v6" />
                    </svg>
                  </button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {selectedFieldId && (
        <p className={styles.description}>Selected field: you can drag its vertices on the map.</p>
      )}

      <div className={styles.fieldPanelActions}>
        <button
          type="button"
          className={`${styles.actionButton} ${styles.analyzeAllButton}`}
          disabled={!ready || fields.length < 2}
          onClick={onAnalyzeAll}
          title={fields.length < 2 ? "Add at least two fields to compare them" : "Analyze and compare all your fields"}
        >
          Analyze all fields
        </button>
        <button
          type="button"
          className={styles.actionButton}
          onClick={onClearFields}
          disabled={!ready || fields.length === 0}
        >
          Delete all fields
        </button>
      </div>
    </section>
  );
}
