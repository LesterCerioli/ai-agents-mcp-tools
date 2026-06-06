"""shadcn/ui integration and component skills."""
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from src.llm.prompts import DESIGN_EXPERT

SHADCN_COMPONENTS = [
    "accordion", "alert", "alert-dialog", "aspect-ratio", "avatar",
    "badge", "breadcrumb", "button", "calendar", "card", "carousel",
    "chart", "checkbox", "collapsible", "command", "context-menu",
    "data-table", "date-picker", "dialog", "drawer", "dropdown-menu",
    "form", "hover-card", "input", "input-otp", "label", "menubar",
    "navigation-menu", "pagination", "popover", "progress", "radio-group",
    "resizable", "scroll-area", "select", "separator", "sheet", "sidebar",
    "skeleton", "slider", "sonner", "switch", "table", "tabs", "textarea",
    "toast", "toggle", "toggle-group", "tooltip",
]


@SkillRegistry.register
class SetupShadcnSkill(BaseSkill):
    name = "design.setup_shadcn"
    description = (
        "Generate the complete shadcn/ui setup: initialization commands, "
        "components.json configuration, and base CSS variables."
    )
    category = SkillCategory.DESIGN
    tags = ["shadcn", "setup", "radix-ui", "component-library"]
    parameters = [
        SkillParameter(
            "style", "shadcn/ui style", required=False, default="default",
            enum=["default", "new-york"],
        ),
        SkillParameter("base_color", "Base color theme", required=False, default="slate",
            enum=["slate", "gray", "zinc", "neutral", "stone"],
        ),
        SkillParameter("components", "Comma-separated initial components to add", required=False, default="button,card,input,form,dialog"),
    ]

    async def execute(  # type: ignore[override]
        self,
        style: str = "default",
        base_color: str = "slate",
        components: str = "button,card,input,form,dialog",
        **_: Any,
    ) -> SkillResult:
        comp_list = [c.strip() for c in components.split(",") if c.strip()]

        components_json = (
            "{\n"
            '  "$schema": "https://ui.shadcn.com/schema.json",\n'
            f'  "style": "{style}",\n'
            '  "rsc": true,\n'
            '  "tsx": true,\n'
            '  "tailwind": {\n'
            '    "config": "tailwind.config.ts",\n'
            '    "css": "app/globals.css",\n'
            '    "baseColor": "' + base_color + '",\n'
            '    "cssVariables": true\n'
            '  },\n'
            '  "aliases": {\n'
            '    "components": "@/components",\n'
            '    "utils": "@/lib/utils",\n'
            '    "ui": "@/components/ui",\n'
            '    "lib": "@/lib",\n'
            '    "hooks": "@/hooks"\n'
            '  }\n'
            '}\n'
        )

        utils_ts = (
            'import { clsx, type ClassValue } from "clsx"\n'
            'import { twMerge } from "tailwind-merge"\n\n'
            'export function cn(...inputs: ClassValue[]) {\n'
            '  return twMerge(clsx(inputs))\n'
            '}\n'
        )

        return SkillResult(
            success=True,
            summary=f"Generated shadcn/ui setup ({style} style, {base_color} base)",
            artifacts=[
                CodeArtifact(filename="components.json", content=components_json, language="json"),
                CodeArtifact(filename="lib/utils.ts", content=utils_ts, language="typescript"),
            ],
            instructions=[
                "Run: npx shadcn@latest init",
                f"Add components: npx shadcn@latest add {' '.join(comp_list)}",
                "All components will be in components/ui/",
            ],
            dependencies=["clsx", "tailwind-merge"],
            dev_dependencies=["tailwindcss", "@tailwindcss/typography"],
        )


@SkillRegistry.register
class GenerateShadcnDataTableSkill(BaseSkill):
    name = "design.generate_data_table"
    description = (
        "Generate a full-featured shadcn/ui DataTable with TanStack Table v8: "
        "sorting, filtering, pagination, row selection, and column visibility."
    )
    category = SkillCategory.DESIGN
    tags = ["data-table", "tanstack-table", "shadcn", "sorting", "pagination"]
    parameters = [
        SkillParameter("entity", "Entity name (e.g. user, product, order, invoice)"),
        SkillParameter(
            "columns",
            "Comma-separated columns with types (e.g. name:string, email:string, status:badge, amount:currency, createdAt:date)",
        ),
        SkillParameter(
            "features",
            "Comma-separated features: sorting, filtering, pagination, selection, column-visibility, export",
            required=False, default="sorting,filtering,pagination",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        entity: str,
        columns: str,
        features: str = "sorting,filtering,pagination",
        **_: Any,
    ) -> SkillResult:
        col_list = [c.strip() for c in columns.split(",") if c.strip()]
        feature_list = [f.strip() for f in features.split(",") if f.strip()]
        entity_title = entity.title()

        prompt = f"""Generate a shadcn/ui DataTable for `{entity_title}` with TanStack Table v8.

Columns: {', '.join(col_list)}
Features: {', '.join(feature_list)}

Generate these files:
1. `components/{entity}/columns.tsx` — column definitions with ColumnDef<{entity_title}>[]
2. `components/{entity}/data-table.tsx` — the table component
3. `components/{entity}/data-table-toolbar.tsx` — search + filters toolbar

Requirements:
- TypeScript with {entity_title} interface
- {"Sortable columns with SortingState" if "sorting" in feature_list else ""}
- {"Global search filter with Input" if "filtering" in feature_list else ""}
- {"Pagination with DataTablePagination component" if "pagination" in feature_list else ""}
- {"Row selection with Checkbox in first column" if "selection" in feature_list else ""}
- {"Column visibility toggle with DropdownMenu" if "column-visibility" in feature_list else ""}
- shadcn/ui Table, Button, Input, Badge components
- Status columns rendered as Badge variants"""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=DESIGN_EXPERT)
        else:
            parsed_cols = []
            for col in col_list:
                parts = col.split(":")
                name = parts[0].strip()
                col_type = parts[1].strip() if len(parts) > 1 else "string"
                parsed_cols.append((name, col_type))

            code = (
                '"use client"\n\n'
                'import { ColumnDef } from "@tanstack/react-table"\n'
                'import { Badge } from "@/components/ui/badge"\n'
                'import { Button } from "@/components/ui/button"\n'
                'import { ArrowUpDown } from "lucide-react"\n\n'
                f"export interface {entity_title} {{\n"
                + "".join(
                    f"  {name}: {'string' if t in ('string', 'badge', 'email') else 'number' if t in ('number', 'currency') else 'Date' if t == 'date' else 'string'}\n"
                    for name, t in parsed_cols
                )
                + "}\n\n"
                f"export const columns: ColumnDef<{entity_title}>[] = [\n"
                + "".join(
                    f"  {{\n"
                    f"    accessorKey: '{name}',\n"
                    f"    header: ({{ column }}) => (\n"
                    f"      <Button variant=\"ghost\" onClick={{() => column.toggleSorting(column.getIsSorted() === 'asc')}}>\n"
                    f"        {name.title()} <ArrowUpDown className=\"ml-2 h-4 w-4\" />\n"
                    f"      </Button>\n"
                    f"    ),\n"
                    + (f"    cell: ({{ row }}) => <Badge variant=\"outline\">{{row.getValue('{name}')}}</Badge>,\n" if t == "badge" else "")
                    + f"  }},\n"
                    for name, t in parsed_cols
                )
                + "]\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated DataTable for `{entity}` with {', '.join(feature_list)}",
            artifacts=[CodeArtifact(filename=f"components/{entity}/columns.tsx", content=code, language="tsx")],
            dependencies=["@tanstack/react-table"],
            instructions=[
                "npx shadcn@latest add table",
                f"npx shadcn@latest add badge button input",
            ],
        )


@SkillRegistry.register
class GenerateShadcnDashboardSkill(BaseSkill):
    name = "design.generate_dashboard"
    description = (
        "Generate a complete admin dashboard layout with shadcn/ui Sidebar, "
        "stat cards, charts, recent activity, and responsive navigation."
    )
    category = SkillCategory.DESIGN
    tags = ["dashboard", "shadcn", "sidebar", "admin", "layout"]
    parameters = [
        SkillParameter("app_name", "Application name"),
        SkillParameter("nav_items", "Comma-separated navigation items (e.g. Dashboard,Users,Products,Orders,Settings)"),
        SkillParameter(
            "widgets",
            "Comma-separated widgets to include: stats-cards, line-chart, bar-chart, pie-chart, recent-table, activity-feed",
            required=False, default="stats-cards,line-chart,recent-table",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        app_name: str,
        nav_items: str,
        widgets: str = "stats-cards,line-chart,recent-table",
        **_: Any,
    ) -> SkillResult:
        nav_list = [n.strip() for n in nav_items.split(",") if n.strip()]
        widget_list = [w.strip() for w in widgets.split(",") if w.strip()]

        prompt = f"""Generate a full admin dashboard for `{app_name}`.

Navigation: {', '.join(nav_list)}
Widgets: {', '.join(widget_list)}

Generate:
1. `app/(app)/dashboard/layout.tsx` — sidebar layout using shadcn Sidebar component
2. `app/(app)/dashboard/page.tsx` — dashboard page with all widgets
3. `components/dashboard/stats-cards.tsx` — KPI stat cards with trend indicators

Requirements:
- shadcn/ui Sidebar (collapsible, with icons)
- Recharts for charts via shadcn chart component
- Responsive: sidebar collapses on mobile
- Dark mode support
- TypeScript throughout
- Lucide icons for navigation items
- Stats cards with % change trend arrows (green up, red down)"""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=DESIGN_EXPERT)
        else:
            nav_items_code = "\n".join(
                f"  {{ title: '{item}', url: '/dashboard/{item.lower()}', icon: LayoutDashboard }},"
                for item in nav_list
            )
            code = (
                '"use client"\n\n'
                'import { LayoutDashboard } from "lucide-react"\n'
                'import { Sidebar, SidebarContent, SidebarHeader, SidebarMenu, SidebarMenuButton, SidebarMenuItem } from "@/components/ui/sidebar"\n\n'
                f"const navItems = [\n{nav_items_code}\n]\n\n"
                f"export function AppSidebar() {{\n"
                "  return (\n"
                "    <Sidebar>\n"
                "      <SidebarHeader>\n"
                f"        <h2 className=\"px-4 text-lg font-semibold\">{app_name}</h2>\n"
                "      </SidebarHeader>\n"
                "      <SidebarContent>\n"
                "        <SidebarMenu>\n"
                "          {navItems.map(item => (\n"
                "            <SidebarMenuItem key={item.title}>\n"
                "              <SidebarMenuButton asChild>\n"
                "                <a href={item.url}><item.icon className=\"mr-2 h-4 w-4\" />{item.title}</a>\n"
                "              </SidebarMenuButton>\n"
                "            </SidebarMenuItem>\n"
                "          ))}\n"
                "        </SidebarMenu>\n"
                "      </SidebarContent>\n"
                "    </Sidebar>\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated dashboard for `{app_name}` with {len(nav_list)} nav items",
            artifacts=[CodeArtifact(filename="components/dashboard/AppSidebar.tsx", content=code, language="tsx")],
            instructions=[
                "npx shadcn@latest add sidebar chart card",
                "npx shadcn@latest add table badge avatar",
            ],
            dependencies=["recharts", "lucide-react"],
        )
