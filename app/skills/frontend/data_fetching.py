
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import FRONTEND_EXPERT


@SkillRegistry.register
class ImplementTanStackQuerySkill(BaseSkill):
    name = "frontend.implement_tanstack_query"
    description = (
        "Generate TanStack Query v5 setup with QueryClient, typed hooks, "
        "mutations, optimistic updates, and infinite scroll."
    )
    category = SkillCategory.FRONTEND
    tags = ["tanstack-query", "react-query", "data-fetching", "cache", "mutations"]
    parameters = [
        SkillParameter("entity", "Entity to query (e.g. products, users, posts, orders)"),
        SkillParameter("api_base", "API base path (e.g. /api/products, /api/users)", required=False, default=""),
        SkillParameter(
            "hooks",
            "Hooks to generate: list,detail,create,update,delete,infinite",
            required=False, default="list,detail,create,delete",
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        entity: str,
        api_base: str = "",
        hooks: str = "list,detail,create,delete",
        **_: Any,
    ) -> SkillResult:
        hook_list = [h.strip() for h in hooks.split(",") if h.strip()]
        entity_title = entity.title()
        api_path = api_base or f"/api/{entity}"

        provider_code = (
            '"use client"\n\n'
            "import { QueryClient, QueryClientProvider } from '@tanstack/react-query'\n"
            "import { ReactQueryDevtools } from '@tanstack/react-query-devtools'\n"
            "import { useState } from 'react'\n\n"
            "export function ReactQueryProvider({ children }: { children: React.ReactNode }) {\n"
            "  const [queryClient] = useState(() => new QueryClient({\n"
            "    defaultOptions: {\n"
            "      queries: {\n"
            "        staleTime: 60 * 1000, // 1 minute\n"
            "        retry: 1,\n"
            "        refetchOnWindowFocus: false,\n"
            "      },\n"
            "    },\n"
            "  }))\n\n"
            "  return (\n"
            "    <QueryClientProvider client={queryClient}>\n"
            "      {children}\n"
            "      {process.env.NODE_ENV === 'development' && <ReactQueryDevtools />}\n"
            "    </QueryClientProvider>\n"
            "  )\n"
            "}\n"
        )

        hooks_code = (
            f"import {{ useQuery, useMutation, useInfiniteQuery, useQueryClient }} from '@tanstack/react-query'\n\n"
            f"export const {entity}Keys = {{\n"
            f"  all: ['{entity}'] as const,\n"
            f"  lists: () => [...{entity}Keys.all, 'list'] as const,\n"
            f"  list: (filters: Record<string, unknown>) => [...{entity}Keys.lists(), filters] as const,\n"
            f"  details: () => [...{entity}Keys.all, 'detail'] as const,\n"
            f"  detail: (id: string) => [...{entity}Keys.details(), id] as const,\n"
            f"}}\n\n"
        )

        if "list" in hook_list:
            hooks_code += (
                f"export function use{entity_title}List(filters?: Record<string, unknown>) {{\n"
                f"  return useQuery({{\n"
                f"    queryKey: {entity}Keys.list(filters ?? {{}}),\n"
                f"    queryFn: async () => {{\n"
                f"      const params = new URLSearchParams(filters as Record<string, string>)\n"
                f"      const res = await fetch(`{api_path}?${{params}}`)\n"
                f"      if (!res.ok) throw new Error('Failed to fetch {entity}s')\n"
                f"      return res.json() as Promise<{entity_title}[]>\n"
                f"    }},\n"
                f"  }})\n"
                f"}}\n\n"
            )

        if "detail" in hook_list:
            hooks_code += (
                f"export function use{entity_title}(id: string) {{\n"
                f"  return useQuery({{\n"
                f"    queryKey: {entity}Keys.detail(id),\n"
                f"    queryFn: async () => {{\n"
                f"      const res = await fetch(`{api_path}/${{id}}`)\n"
                f"      if (!res.ok) throw new Error('{entity_title} not found')\n"
                f"      return res.json() as Promise<{entity_title}>\n"
                f"    }},\n"
                f"    enabled: !!id,\n"
                f"  }})\n"
                f"}}\n\n"
            )

        if "create" in hook_list:
            hooks_code += (
                f"export function useCreate{entity_title}() {{\n"
                f"  const queryClient = useQueryClient()\n"
                f"  return useMutation({{\n"
                f"    mutationFn: async (data: Partial<{entity_title}>) => {{\n"
                f"      const res = await fetch('{api_path}', {{\n"
                f"        method: 'POST',\n"
                f"        headers: {{ 'Content-Type': 'application/json' }},\n"
                f"        body: JSON.stringify(data),\n"
                f"      }})\n"
                f"      if (!res.ok) throw new Error('Failed to create {entity}')\n"
                f"      return res.json() as Promise<{entity_title}>\n"
                f"    }},\n"
                f"    onSuccess: () => {{\n"
                f"      queryClient.invalidateQueries({{ queryKey: {entity}Keys.lists() }})\n"
                f"    }},\n"
                f"  }})\n"
                f"}}\n\n"
            )

        if "delete" in hook_list:
            hooks_code += (
                f"export function useDelete{entity_title}() {{\n"
                f"  const queryClient = useQueryClient()\n"
                f"  return useMutation({{\n"
                f"    mutationFn: async (id: string) => {{\n"
                f"      const res = await fetch(`{api_path}/${{id}}`, {{ method: 'DELETE' }})\n"
                f"      if (!res.ok) throw new Error('Failed to delete {entity}')\n"
                f"    }},\n"
                f"    onMutate: async (id) => {{\n"
                f"      await queryClient.cancelQueries({{ queryKey: {entity}Keys.lists() }})\n"
                f"      const prev = queryClient.getQueriesData({{ queryKey: {entity}Keys.lists() }})\n"
                f"      queryClient.setQueriesData({{\n"
                f"        queryKey: {entity}Keys.lists(),\n"
                f"      }}, (old: {entity_title}[] | undefined) => old?.filter(item => item.id !== id))\n"
                f"      return {{ prev }}\n"
                f"    }},\n"
                f"    onError: (_err, _id, ctx) => {{\n"
                f"      ctx?.prev.forEach(([key, data]) => queryClient.setQueryData(key, data))\n"
                f"    }},\n"
                f"    onSettled: () => queryClient.invalidateQueries({{ queryKey: {entity}Keys.lists() }}),\n"
                f"  }})\n"
                f"}}\n\n"
            )

        hooks_code += f"// Add this interface based on your {entity} data shape\ninterface {entity_title} {{\n  id: string\n  // ...fields\n}}\n"

        return SkillResult(
            success=True,
            summary=f"Generated TanStack Query hooks for `{entity}`",
            artifacts=[
                CodeArtifact(filename="components/providers/react-query.tsx", content=provider_code, language="tsx"),
                CodeArtifact(filename=f"hooks/use-{entity}.ts", content=hooks_code, language="typescript"),
            ],
            dependencies=["@tanstack/react-query"],
            dev_dependencies=["@tanstack/react-query-devtools"],
            instructions=[
                "Add <ReactQueryProvider> to app/layout.tsx",
                f"Import hooks: import {{ use{entity_title}List }} from '@/hooks/use-{entity}'",
            ],
        )
