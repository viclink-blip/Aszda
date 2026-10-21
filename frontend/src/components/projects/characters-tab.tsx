"use client";

import { Pencil, Plus, Trash2, UserRound, Wand2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { AssetMedia } from "@/components/assets/asset-media";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import type { Character } from "@/lib/types";
import { CharacterFormDialog } from "./character-form-dialog";
import type { ProjectTabProps } from "./project-workspace";

export function CharactersTab({ detail, update }: ProjectTabProps) {
  const projectId = detail.project.id;
  const toast = useToast();
  // editing: undefined = closed, null = new character, Character = edit it.
  const [editing, setEditing] = useState<Character | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<Character | null>(null);

  const saved = (character: Character) => {
    update((d) => {
      const exists = d.characters.some((c) => c.id === character.id);
      return {
        ...d,
        characters: exists ? d.characters.map((c) => (c.id === character.id ? character : c)) : [...d.characters, character],
      };
    });
    toast.success(editing ? "Character saved" : "Character added", character.name);
  };

  const remove = async () => {
    if (!deleting) return;
    try {
      await api.characters.remove(projectId, deleting.id);
    } catch (error) {
      throw new Error(errorMessage(error));
    }
    const id = deleting.id;
    update((d) => ({
      ...d,
      characters: d.characters.filter((c) => c.id !== id),
      // Scenes no longer list a deleted character.
      scenes: d.scenes.map((s) => ({ ...s, character_ids: s.character_ids.filter((cid) => cid !== id) })),
    }));
    toast.success("Character deleted");
  };

  return (
    <section aria-labelledby="characters-heading">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="characters-heading" className="font-display text-lg font-semibold text-fg">Characters</h2>
          <p className="text-sm text-muted">The cast of this project, with reference images for a consistent look.</p>
        </div>
        <Button onClick={() => setEditing(null)}><Plus className="h-4 w-4" aria-hidden /> Add character</Button>
      </div>

      {detail.characters.length === 0 ? (
        <EmptyState
          icon={UserRound}
          title="No characters yet"
          description="Add the people, creatures or mascots in your story. A reference image lets you animate them later."
          action={<Button onClick={() => setEditing(null)}><Plus className="h-4 w-4" aria-hidden /> Add character</Button>}
        />
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {detail.characters.map((character) => (
            <li key={character.id} className="flex flex-col overflow-hidden rounded-xl border border-line bg-surface">
              {character.reference_asset_id ? (
                <AssetMedia asset={{ id: character.reference_asset_id, kind: "image", display_name: `${character.name} reference` }} compact className="rounded-none" />
              ) : (
                <div className="flex aspect-video items-center justify-center bg-surface-2 text-xs text-subtle">No reference image</div>
              )}
              <div className="flex flex-1 flex-col p-4">
                <h3 className="font-display font-semibold text-fg">{character.name}</h3>
                <p className="mt-1 line-clamp-3 flex-1 text-sm text-muted">{character.description || "No description."}</p>
                <div className="mt-4 flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" onClick={() => setEditing(character)}>
                    <Pencil className="h-3.5 w-3.5" aria-hidden /> Edit
                  </Button>
                  {character.reference_asset_id && (
                    <Link
                      href={`/app/studio/animation?project=${projectId}&character=${character.id}`}
                      className="inline-flex h-8 items-center gap-1.5 rounded-lg px-3 text-sm text-muted hover:bg-surface-2 hover:text-fg"
                    >
                      <Wand2 className="h-3.5 w-3.5" aria-hidden /> Animate
                    </Link>
                  )}
                  <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setDeleting(character)} aria-label={`Delete ${character.name}`}>
                    <Trash2 className="h-3.5 w-3.5" aria-hidden />
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}

      {editing !== undefined && (
        <CharacterFormDialog
          // A new key resets the form for each character.
          key={editing?.id ?? "new"}
          projectId={projectId}
          character={editing}
          open
          onOpenChange={(open) => !open && setEditing(undefined)}
          onSaved={saved}
        />
      )}
      <ConfirmDialog
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete character?"
        description={<>Delete <strong className="text-fg">{deleting?.name}</strong>? They will be removed from every scene. Their reference image stays in Assets.</>}
        confirmLabel="Delete"
        destructive
        onConfirm={remove}
      />
    </section>
  );
}
