
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import NEXTJS_EXPERT


@SkillRegistry.register
class GenerateServerActionSkill(BaseSkill):
    name = "nextjs.generate_server_action"
    description = (
        "Generate a Next.js Server Action with Zod validation, error handling, "
        "revalidatePath/revalidateTag, and proper TypeScript types."
    )
    category = SkillCategory.NEXTJS
    tags = ["server-action", "mutation", "zod", "revalidate"]
    parameters = [
        SkillParameter("name", "Action function name (e.g. createProduct, updateUser, deletePost)"),
        SkillParameter("description", "What the action does (e.g. creates a product in the database)"),
        SkillParameter("inputs", "Comma-separated input fields (e.g. title:string, price:number, userId:string)"),
        SkillParameter(
            "revalidate", "Path or tag to revalidate after mutation (e.g. /products, products)",
            required=False, default="",
        ),
        SkillParameter(
            "db", "Database/ORM being used", required=False, default="prisma",
            enum=["prisma", "drizzle", "supabase", "raw"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        description: str,
        inputs: str,
        revalidate: str = "",
        db: str = "prisma",
        **_: Any,
    ) -> SkillResult:
        input_list = [i.strip() for i in inputs.split(",") if i.strip()]

        prompt = f"""Generate a Next.js Server Action called `{name}`.

What it does: {description}
Input fields: {', '.join(input_list)}
Database/ORM: {db}
{"Revalidate: " + revalidate if revalidate else ""}

Requirements:
- 'use server' directive at the top of the file
- Zod schema for input validation
- Return type: `{{ success: true, data: T }} | {{ success: false, error: string }}`
- auth() check from next-auth to ensure authenticated user
- Wrap database call in try/catch
- {"revalidatePath('" + revalidate + "')" if revalidate.startswith("/") else "revalidateTag('" + revalidate + "')" if revalidate else "No revalidation needed"}
- Proper TypeScript types throughout
- Handle Zod parse errors and database errors separately

Generate the complete server action file `actions/{name}.ts`."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="typescript", context=NEXTJS_EXPERT)
        else:
            code = (
                '"use server"\n\n'
                "import { z } from 'zod'\n"
                "import { revalidatePath } from 'next/cache'\n"
                "import { auth } from '@/auth'\n\n"
                f"const {name}Schema = z.object({{\n"
                "  // Add your input fields here\n"
                "})\n\n"
                f"export async function {name}(input: unknown) {{\n"
                "  const session = await auth()\n"
                "  if (!session?.user) {\n"
                "    return { success: false, error: 'Unauthorized' } as const\n"
                "  }\n\n"
                "  const parsed = " + name + "Schema.safeParse(input)\n"
                "  if (!parsed.success) {\n"
                "    return { success: false, error: parsed.error.message } as const\n"
                "  }\n\n"
                "  try {\n"
                "    // Database operation here\n"
                f"    {'revalidatePath(' + repr(revalidate) + ')' if revalidate else '// No revalidation'}\n"
                "    return { success: true, data: parsed.data } as const\n"
                "  } catch (error) {\n"
                "    return { success: false, error: 'Operation failed' } as const\n"
                "  }\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated server action `{name}`",
            artifacts=[CodeArtifact(
                filename=f"actions/{name}.ts", content=code, language="typescript",
            )],
            dependencies=["zod", "next-auth"],
            next_steps=[
                f"Import with: import {{ {name} }} from '@/actions/{name}'",
                "Bind to a form with useActionState()",
                "Or call directly from a server component",
            ],
        )


@SkillRegistry.register
class ImplementOptimisticUpdateSkill(BaseSkill):
    name = "nextjs.implement_optimistic_update"
    description = (
        "Implement optimistic UI updates using React 19 useOptimistic hook "
        "for instant feedback while server mutation is in flight."
    )
    category = SkillCategory.NEXTJS
    tags = ["optimistic-ui", "useOptimistic", "server-action", "ux"]
    parameters = [
        SkillParameter("component_name", "Name of the component that needs optimistic updates"),
        SkillParameter("entity", "Entity being mutated (e.g. post, comment, todo, like)"),
        SkillParameter(
            "operations",
            "Comma-separated CRUD operations to optimize: create, update, delete, toggle",
            required=False, default="create,delete",
        ),
        SkillParameter("list_type", "How items are displayed (e.g. list, grid, table)", required=False, default="list"),
    ]

    async def execute(  # type: ignore[override]
        self,
        component_name: str,
        entity: str,
        operations: str = "create,delete",
        list_type: str = "list",
        **_: Any,
    ) -> SkillResult:
        op_list = [o.strip() for o in operations.split(",") if o.strip()]

        prompt = f"""Generate a React 19 component `{component_name}` with optimistic updates for `{entity}`.

Operations to optimize: {', '.join(op_list)}
Display: {list_type} of {entity}s

Requirements:
- 'use client' directive
- useOptimistic(items, reducerFn) from React 19
- useTransition for pending state
- For each operation in [{', '.join(op_list)}]:
  - Immediately apply optimistic update to UI
  - Call server action in background
  - Revert on failure with error toast
- TypeScript types for {entity} and optimistic actions
- Show pending indicator on in-flight items
- Accessible: aria-live for list updates

Generate the complete {component_name}.tsx with all hooks and handlers."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=NEXTJS_EXPERT)
        else:
            code = (
                '"use client"\n\n'
                "import { useOptimistic, useTransition } from 'react'\n"
                "import { toast } from 'sonner'\n\n"
                f"interface {entity.title()} {{\n"
                "  id: string\n"
                "  // Add fields\n"
                "}\n\n"
                f"interface {component_name}Props {{\n"
                f"  initial{entity.title()}s: {entity.title()}[]\n"
                "}\n\n"
                f"export function {component_name}({{ initial{entity.title()}s }}: {component_name}Props) {{\n"
                "  const [isPending, startTransition] = useTransition()\n"
                f"  const [optimistic{entity.title()}s, addOptimistic] = useOptimistic(\n"
                f"    initial{entity.title()}s,\n"
                f"    (state: {entity.title()}[], action: {{ type: 'delete'; id: string }}) => {{\n"
                "      if (action.type === 'delete') return state.filter(item => item.id !== action.id)\n"
                "      return state\n"
                "    }}\n"
                "  )\n\n"
                f"  function handleDelete(id: string) {{\n"
                "    startTransition(async () => {\n"
                "      addOptimistic({ type: 'delete', id })\n"
                "      // const result = await delete" + entity.title() + "(id)\n"
                "      // if (!result.success) toast.error('Failed to delete')\n"
                "    })\n"
                "  }\n\n"
                "  return (\n"
                "    <ul aria-live=\"polite\" className=\"space-y-2\">\n"
                f"      {{optimistic{entity.title()}s.map(item => (\n"
                "        <li key={item.id} className=\"flex items-center justify-between rounded-lg border p-3\">\n"
                "          <span>{item.id}</span>\n"
                "          <button onClick={() => handleDelete(item.id)} disabled={isPending}>Delete</button>\n"
                "        </li>\n"
                "      ))}}\n"
                "    </ul>\n"
                "  )\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated optimistic UI component `{component_name}`",
            artifacts=[CodeArtifact(filename=f"components/{component_name}.tsx", content=code, language="tsx")],
            dependencies=["sonner"],
            next_steps=[
                "Create the matching Server Actions for each operation",
                "Pass server data as initial props from parent Server Component",
            ],
        )


@SkillRegistry.register
class GenerateCRUDActionsSkill(BaseSkill):
    name = "nextjs.generate_crud_actions"
    description = (
        "Generate a complete set of CRUD Server Actions (create, read, update, delete) "
        "for an entity with Zod validation, auth checks, and cache revalidation."
    )
    category = SkillCategory.NEXTJS
    tags = ["crud", "server-action", "database", "zod"]
    parameters = [
        SkillParameter("entity", "Entity name (e.g. product, user, post, order)"),
        SkillParameter(
            "fields",
            "Comma-separated fields with types (e.g. title:string, price:number, published:boolean)",
        ),
        SkillParameter(
            "db", "ORM/database", required=False, default="prisma",
            enum=["prisma", "drizzle", "supabase"],
        ),
        SkillParameter("route", "Route to revalidate (e.g. /products, /dashboard/posts)", required=False, default=""),
    ]

    async def execute(  # type: ignore[override]
        self,
        entity: str,
        fields: str,
        db: str = "prisma",
        route: str = "",
        **_: Any,
    ) -> SkillResult:
        field_list = [f.strip() for f in fields.split(",") if f.strip()]
        entity_title = entity.title()

        prompt = f"""Generate complete CRUD Server Actions for the `{entity}` entity.

Fields: {', '.join(field_list)}
ORM: {db}
{"Revalidate route: " + route if route else ""}

Generate these 5 actions in `actions/{entity}.ts`:
1. `create{entity_title}(input)` — validate, insert, revalidate, return result
2. `get{entity_title}(id)` — fetch single record with auth check
3. `getAll{entity_title}s(params?)` — fetch list with optional pagination/filtering
4. `update{entity_title}(id, input)` — validate, update, revalidate
5. `delete{entity_title}(id)` — auth check, soft-delete or hard-delete, revalidate

Requirements:
- Single file with 'use server' at top
- Shared Zod schemas for create and update
- Return `{{ success: true, data }} | {{ success: false, error }}`
- auth() check on mutating actions
- Proper TypeScript return types"""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="typescript", context=NEXTJS_EXPERT)
        else:
            code = (
                '"use server"\n\n'
                "import { z } from 'zod'\n"
                "import { revalidatePath } from 'next/cache'\n\n"
                f"const {entity_title}Schema = z.object({{\n"
                "  " + "\n  ".join(f"{f.split(':')[0]}: z.{f.split(':')[1] if ':' in f else 'string'}()," for f in field_list) + "\n"
                "})\n\n"
                f"export async function create{entity_title}(input: unknown) {{\n"
                f"  const parsed = {entity_title}Schema.safeParse(input)\n"
                "  if (!parsed.success) return { success: false, error: parsed.error.message } as const\n"
                "  try {\n"
                "    // const data = await db." + entity + ".create({ data: parsed.data })\n"
                f"    {'revalidatePath(' + repr(route) + ')' if route else '// No revalidation'}\n"
                "    return { success: true, data: parsed.data } as const\n"
                "  } catch { return { success: false, error: 'Create failed' } as const }\n"
                "}\n\n"
                f"export async function delete{entity_title}(id: string) {{\n"
                "  try {\n"
                "    // await db." + entity + ".delete({ where: { id } })\n"
                f"    {'revalidatePath(' + repr(route) + ')' if route else '// No revalidation'}\n"
                "    return { success: true } as const\n"
                "  } catch { return { success: false, error: 'Delete failed' } as const }\n"
                "}\n"
            )

        return SkillResult(
            success=True,
            summary=f"Generated complete CRUD actions for `{entity}`",
            artifacts=[CodeArtifact(filename=f"actions/{entity}.ts", content=code, language="typescript")],
            dependencies=["zod", "next-auth"],
        )
