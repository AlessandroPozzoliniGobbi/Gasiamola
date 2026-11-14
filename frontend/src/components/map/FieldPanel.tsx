"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import type { FieldItem } from "../../types/field";
import styles from "../../styles/map.module.css";

type Props = {
  fields: FieldItem[];
  selectedFieldId: string | null;
  onSelectField: (id: string) => void;
  onRenameField: (id: string, name: string) => void;
  onDeleteField: (id: string) => void;
  onClearFields: () => void;
  ready: boolean;
};

export default function FieldPanel({
  fields,
  selectedFieldId,
  onSelectField,
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
      <h2 className={styles.sectionTitle}>I tuoi appezzamenti ({fields.length})</h2>
      {fields.length === 0 ? (
        <p className={styles.description}>Non hai ancora disegnato alcun campo.</p>
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
                    aria-label={`Nuovo nome dell'appezzamento ${field.number}`}
                  />
                  <button type="submit" className={styles.fieldIconButton} aria-label="Salva nome" title="Salva nome">✓</button>
                  <button type="button" className={styles.fieldIconButton} onClick={() => setEditingId(null)} aria-label="Annulla rinomina" title="Annulla rinomina">×</button>
                </form>
              ) : (
                <>
                  <button
                    type="button"
                    className={[styles.fieldSelectButton, selectedFieldId === field.id ? styles.fieldSelectActive : ""].join(" ")}
                    onClick={() => onSelectField(field.id)}
                    aria-pressed={selectedFieldId === field.id}
                    title="Seleziona e inquadra il campo"
                  >
                    {field.name}
                  </button>
                  <button
                    type="button"
                    className={styles.fieldIconButton}
                    onClick={() => beginEditing(field)}
                    disabled={!ready}
                    title={`Rinomina ${field.name}`}
                    aria-label={`Rinomina ${field.name}`}
                  >
                    ✎
                  </button>
                  <button
                    type="button"
                    className={[styles.fieldIconButton, styles.fieldDeleteButton].join(" ")}
                    onClick={() => onDeleteField(field.id)}
                    disabled={!ready}
                    title={`Elimina ${field.name}`}
                    aria-label={`Elimina ${field.name}`}
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
        <p className={styles.description}>Campo selezionato: puoi trascinarne i vertici sulla mappa.</p>
      )}

      <button
        type="button"
        className={styles.actionButton}
        onClick={onClearFields}
        disabled={!ready || fields.length === 0}
      >
        Cancella tutti gli appezzamenti
      </button>
    </section>
  );
}
