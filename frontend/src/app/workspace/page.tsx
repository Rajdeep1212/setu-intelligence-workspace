import type { Metadata } from "next";
import { Providers } from "@/components/providers";
import { WorkspaceDemo } from "@/components/workspace/workspace-demo";
export const metadata: Metadata = { title: "Workspace" };
export default function WorkspacePage() { return <Providers><WorkspaceDemo /></Providers>; }
