
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import FRONTEND_EXPERT


@SkillRegistry.register
class ImplementZustandStoreSkill(BaseSkill):
    name = "frontend.implement_zustand_store"
    description = (
        "Generate a Zustand store with TypeScript, devtools, persist middleware, "
        "and custom selectors for a specific application domain."
    )
    category = SkillCategory.FRONTEND
    tags = ["state", "zustand", "store", "client-state"]
    parameters = [
        SkillParameter("name", "Store name (e.g. cart, auth, ui, editor, player)"),
        SkillParameter("state_fields", "Comma-separated state fields with types (e.g. items:CartItem[],total:number,isOpen:boolean)"),
        SkillParameter("actions", "Comma-separated action names (e.g. addItem,removeItem,clearCart,toggleOpen)"),
        SkillParameter("persist", "Persist state to localStorage", required=False, default="false", enum=["true", "false"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        state_fields: str,
        actions: str,
        persist: str = "false",
        **_: Any,
    ) -> SkillResult:
        fields = [f.strip() for f in state_fields.split(",") if f.strip()]
        action_list = [a.strip() for a in actions.split(",") if a.strip()]
        store_name = name.title().replace(" ", "")

        prompt = f"""Generate a Zustand store called `use{store_name}Store`.

State: {', '.join(fields)}
Actions: {', '.join(action_list)}
Persist: {persist}

Requirements:
- TypeScript with strict types
- Interface for State, Interface for Actions
- Combined interface: {store_name}Store = {store_name}State & {store_name}Actions
- {"Wrap with persist() middleware, key: '{name}-store'" if persist == "true" else "No persistence"}
- Wrap with devtools() for Redux DevTools
- Typed selectors as separate hooks (e.g. const useCartTotal = () => useCartStore(state => state.total))
- Immer-style mutations if appropriate for arrays/objects
- Export: useStore, individual selectors

Generate `stores/{name}.ts`."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="typescript", context=FRONTEND_EXPERT)
        else:
            state_interface = "\n".join(
                f"  {f.split(':')[0]}: {f.split(':')[1] if ':' in f else 'unknown'}"
                for f in fields
            )
            actions_interface = "\n".join(f"  {a}: (...args: unknown[]) => void" for a in action_list)

            code = (
                f"import {{ create }} from 'zustand'\n"
                f"import {{ devtools{',' if persist == 'true' else '' } {'persist' if persist == 'true' else ''} }} from 'zustand/middleware'\n\n"
                f"interface {store_name}State {{\n{state_interface}\n}}\n\n"
                f"interface {store_name}Actions {{\n{actions_interface}\n}}\n\n"
                f"type {store_name}Store = {store_name}State & {store_name}Actions\n\n"
                f"export const use{store_name}Store = create<{store_name}Store>()(\n"
                f"  devtools(\n"
                f"    (set, get) => ({{\n"
                + "".join(
                    f"      {f.split(':')[0]}: {repr([] if '[]' in f else False if 'boolean' in f else 0 if 'number' in f else None)},\n"
                    for f in fields
                )
                + "".join(f"      {a}: () => set((state) => state),\n" for a in action_list)
                + f"    }}),\n"
                f"    {{ name: '{name}-store' }}\n"
                f"  )\n"
                f")\n\n"
                + "".join(
                    f"export const use{store_name + f.split(':')[0].title()} = () => use{store_name}Store(state => state.{f.split(':')[0]})\n"
                    for f in fields
                )
            )

        return SkillResult(
            success=True,
            summary=f"Generated Zustand store `use{store_name}Store`",
            artifacts=[CodeArtifact(filename=f"stores/{name}.ts", content=code, language="typescript")],
            dependencies=["zustand"],
        )


@SkillRegistry.register
class ImplementJotaiAtomsSkill(BaseSkill):
    name = "frontend.implement_jotai_atoms"
    description = (
        "Generate Jotai atoms for atomic state management with derived atoms, "
        "async atoms, and atom families for entity collections."
    )
    category = SkillCategory.FRONTEND
    tags = ["state", "jotai", "atoms", "atomic-state"]
    parameters = [
        SkillParameter("domain", "State domain (e.g. todos, filters, user, theme, cart)"),
        SkillParameter("atoms", "Comma-separated atom definitions (e.g. selectedId:string|null, filter:active|all|done, showModal:boolean)"),
        SkillParameter("derived", "Comma-separated derived atom descriptions (e.g. filteredItems:filter todos by current filter)", required=False, default=""),
    ]

    async def execute(  # type: ignore[override]
        self,
        domain: str,
        atoms: str,
        derived: str = "",
        **_: Any,
    ) -> SkillResult:
        atom_list = [a.strip() for a in atoms.split(",") if a.strip()]
        derived_list = [d.strip() for d in derived.split(",") if d.strip()] if derived else []

        code = (
            "import { atom, atomFamily } from 'jotai'\n\n"
            f"// Base atoms for {domain}\n"
        )

        for atom_def in atom_list:
            parts = atom_def.split(":")
            atom_name = parts[0].strip()
            atom_types = parts[1].strip() if len(parts) > 1 else "unknown"
            is_enum = "|" in atom_types
            default_val = f"'{atom_types.split('|')[0]}'" if is_enum else "null" if "null" in atom_types else "false" if "boolean" in atom_types else "0" if atom_types == "number" else "''"
            sep = "' | '"
            type_annotation = f"'{atom_types.replace('|', sep)}'" if is_enum else atom_types

            code += f"export const {atom_name}Atom = atom<{type_annotation if not is_enum else 'string'}>({default_val})\n"

        if derived_list:
            code += "\n// Derived atoms\n"
            for derived_def in derived_list:
                parts = derived_def.split(":")
                name = parts[0].strip()
                desc = parts[1].strip() if len(parts) > 1 else ""
                code += (
                    f"// {desc}\n"
                    f"export const {name}Atom = atom((get) => {{\n"
                    f"  // Derive from base atoms\n"
                    f"  return get({atom_list[0].split(':')[0]}Atom)\n"
                    f"}})\n\n"
                )

        return SkillResult(
            success=True,
            summary=f"Generated {len(atom_list)} Jotai atoms for `{domain}`",
            artifacts=[CodeArtifact(filename=f"atoms/{domain}.ts", content=code, language="typescript")],
            dependencies=["jotai"],
        )


@SkillRegistry.register
class ImplementUIStoreSkill(BaseSkill):
    name = "frontend.implement_ui_store"
    description = (
        "Generate a UI state store for modals, drawers, toast queues, "
        "loading indicators, and global UI state with Zustand."
    )
    category = SkillCategory.FRONTEND
    tags = ["state", "zustand", "ui-state", "modals", "toasts"]
    parameters = [
        SkillParameter(
            "features",
            "Comma-separated UI features to manage: modals, drawers, toasts, loading, sidebar, command-palette",
            required=False, default="modals,drawers,toasts,loading",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        features: str = "modals,drawers,toasts,loading",
        **_: Any,
    ) -> SkillResult:
        feature_list = [f.strip() for f in features.split(",") if f.strip()]

        code = (
            "import { create } from 'zustand'\n"
            "import { devtools } from 'zustand/middleware'\n\n"
            "type ModalId = string\n"
            "type DrawerId = string\n\n"
            "interface UIState {\n"
        )

        if "modals" in feature_list:
            code += "  openModals: Set<ModalId>\n"
        if "drawers" in feature_list:
            code += "  openDrawers: Set<DrawerId>\n"
        if "loading" in feature_list:
            code += "  loadingKeys: Set<string>\n"
        if "sidebar" in feature_list:
            code += "  sidebarOpen: boolean\n"

        code += "}\n\ninterface UIActions {\n"

        if "modals" in feature_list:
            code += "  openModal: (id: ModalId) => void\n  closeModal: (id: ModalId) => void\n  closeAllModals: () => void\n"
        if "drawers" in feature_list:
            code += "  openDrawer: (id: DrawerId) => void\n  closeDrawer: (id: DrawerId) => void\n"
        if "loading" in feature_list:
            code += "  setLoading: (key: string, loading: boolean) => void\n  isLoading: (key: string) => boolean\n"
        if "sidebar" in feature_list:
            code += "  toggleSidebar: () => void\n  setSidebar: (open: boolean) => void\n"

        code += "}\n\ntype UIStore = UIState & UIActions\n\n"
        code += "export const useUIStore = create<UIStore>()(devtools((set, get) => ({\n"

        if "modals" in feature_list:
            code += (
                "  openModals: new Set(),\n"
                "  openModal: (id) => set(s => ({ openModals: new Set([...s.openModals, id]) })),\n"
                "  closeModal: (id) => set(s => { const m = new Set(s.openModals); m.delete(id); return { openModals: m } }),\n"
                "  closeAllModals: () => set({ openModals: new Set() }),\n"
            )
        if "drawers" in feature_list:
            code += (
                "  openDrawers: new Set(),\n"
                "  openDrawer: (id) => set(s => ({ openDrawers: new Set([...s.openDrawers, id]) })),\n"
                "  closeDrawer: (id) => set(s => { const d = new Set(s.openDrawers); d.delete(id); return { openDrawers: d } }),\n"
            )
        if "loading" in feature_list:
            code += (
                "  loadingKeys: new Set(),\n"
                "  setLoading: (key, loading) => set(s => {\n"
                "    const keys = new Set(s.loadingKeys)\n"
                "    loading ? keys.add(key) : keys.delete(key)\n"
                "    return { loadingKeys: keys }\n"
                "  }),\n"
                "  isLoading: (key) => get().loadingKeys.has(key),\n"
            )
        if "sidebar" in feature_list:
            code += (
                "  sidebarOpen: true,\n"
                "  toggleSidebar: () => set(s => ({ sidebarOpen: !s.sidebarOpen })),\n"
                "  setSidebar: (open) => set({ sidebarOpen: open }),\n"
            )

        code += "}), { name: 'ui-store' }))\n\n"
        code += "// Convenience selectors\n"
        if "modals" in feature_list:
            code += "export const useModal = (id: ModalId) => ({\n  isOpen: useUIStore(s => s.openModals.has(id)),\n  open: () => useUIStore.getState().openModal(id),\n  close: () => useUIStore.getState().closeModal(id),\n})\n"

        return SkillResult(
            success=True,
            summary=f"Generated UI store with: {', '.join(feature_list)}",
            artifacts=[CodeArtifact(filename="stores/ui.ts", content=code, language="typescript")],
            dependencies=["zustand"],
        )
