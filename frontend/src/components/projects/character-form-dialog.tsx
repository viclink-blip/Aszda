"use client";

import { useRef, useState } from "react";
import { AssetPicker } from "@/components/assets/asset-picker";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, FormError } from "@/components/ui/field";
import { Input, Textarea } from "@/components/ui/input";
import { api } from "@/lib/api";
import { focusFirstError, splitErrors } from "@/lib/forms";
import type { Character } from "@/lib/types";

/** Add or edit a character. `character` = null means "add". */
export function CharacterFormDialog({ projectId, character, open, onOpenChange, onSaved }: {
  projectId: string;
  character: Character | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (character: Character) => void;
}) {
  const formRef = useRef<HTMLFormElement>(null);
  const [name, setName] = useState(character?.name ?? "");
  const [description, setDescription] = useState(character?.description ?? "");
  const [referenceId, setReferenceId] = useState<string | null>(character?.reference_asset_id ?? null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) {
      setErrors({ name: "Give the character a name." });
      focusFirstError(formRef.current);
      return;
    }
    setBusy(true);
    setErrors({});
    setFormError(null);
    const body = { name: name.trim(), description: description.trim(), reference_asset_id: referenceId };
    try {
      const { character: saved } = character
        ? await api.characters.update(projectId, character.id, body)
        : await api.characters.create(projectId, body);
      onSaved(saved);
      onOpenChange(false);
    } catch (error) {
      const split = splitErrors(error, ["name", "description", "reference_asset_id"]);
      setErrors(split.fieldErrors);
      setFormError(split.formError);
      focusFirstError(formRef.current);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={character ? "Edit character" : "Add character"} size="lg">
      <form ref={formRef} onSubmit={submit} noValidate className="flex flex-col gap-4">
        <FormError message={formError} />
        <Field label="Name" required error={errors.name}>
          {(p) => <Input {...p} maxLength={80} value={name} onChange={(e) => setName(e.target.value)} autoFocus />}
        </Field>
        <Field
          label="Description"
          error={errors.description}
          help="Appearance, clothing, personality, voice. Specific visual details help keep a consistent look."
        >
          {(p) => <Textarea {...p} rows={4} maxLength={5000} value={description} onChange={(e) => setDescription(e.target.value)} />}
        </Field>
        <AssetPicker
          projectId={projectId}
          label="Reference image"
          value={referenceId}
          onChange={setReferenceId}
          invalid={Boolean(errors.reference_asset_id)}
        />
        {errors.reference_asset_id && <p className="-mt-2 text-xs text-danger" role="alert">{errors.reference_asset_id}</p>}
        <p className="-mt-1 text-xs text-subtle">The Animation Studio uses this image as the starting frame when animating the character.</p>
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" loading={busy}>{character ? "Save character" : "Add character"}</Button>
        </div>
      </form>
    </Dialog>
  );
}
