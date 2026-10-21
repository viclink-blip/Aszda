/**
 * Product facts shown on the marketing site and in the app.
 * Keep this honest: only list something as available when it works today.
 */

import { AudioLines, Clapperboard, FileText, Film, ImageIcon, type LucideIcon, PenLine, Scissors, Sparkles, Wallet, Wand2 } from "lucide-react";

export interface Studio {
  slug: "script" | "video" | "animation" | "voice";
  name: string;
  href: string;
  icon: LucideIcon;
  summary: string;
  provider: string;
}

export const STUDIOS: Studio[] = [
  {
    slug: "script",
    name: "Script Studio",
    href: "/app/studio/script",
    icon: PenLine,
    summary: "Develop a story concept, draft a script, outline characters or break a story into scenes.",
    provider: "Anthropic Claude",
  },
  {
    slug: "video",
    name: "Video Studio",
    href: "/app/studio/video",
    icon: Film,
    summary: "Generate short video clips from a text prompt, or from a reference image used as the first frame.",
    provider: "Runway",
  },
  {
    slug: "animation",
    name: "Animation Studio",
    href: "/app/studio/animation",
    icon: Wand2,
    summary: "Bring a character to life: animate a character's still reference image into a short clip for a scene.",
    provider: "Runway",
  },
  {
    slug: "voice",
    name: "Voice Studio",
    href: "/app/studio/voice",
    icon: AudioLines,
    summary: "Turn narration and dialogue into speech with a choice of voices, formats and speaking styles.",
    provider: "OpenAI",
  },
];

export interface PlannedFeature {
  name: string;
  icon: LucideIcon;
  summary: string;
}

/** Features that do NOT exist yet. Always labelled "Planned" in the UI. */
export const PLANNED: PlannedFeature[] = [
  {
    name: "AI Film Director",
    icon: Clapperboard,
    summary: "A guided workflow from story to finished film: concept, script, characters, storyboard, review and generation.",
  },
  {
    name: "Image generation",
    icon: ImageIcon,
    summary: "Create character designs, key frames and storyboard images directly in ASZDA.",
  },
  {
    name: "Export and assembly",
    icon: Scissors,
    summary: "Stitch scenes, voice and music into one exported film.",
  },
  {
    name: "Voice cloning",
    icon: Sparkles,
    summary: "Not offered today. If it is ever added, it will require clear consent from the voice owner.",
  },
  {
    name: "Payments and credit packs",
    icon: Wallet,
    summary: "Buying credits is not active yet. The credits-based pricing model is still being designed.",
  },
];

/** The providers ASZDA works with today (no proprietary models). */
export const PROVIDERS = [
  { name: "Anthropic Claude", role: "Writing — story concepts, scripts, characters and scene breakdowns", icon: FileText },
  { name: "OpenAI", role: "Voice — text-to-speech narration and dialogue", icon: AudioLines },
  { name: "Runway", role: "Video — text-to-video and image-to-video clips", icon: Film },
];

export const CONTACT_EMAIL = "hello@aszda.example"; // placeholder: replace before launch
