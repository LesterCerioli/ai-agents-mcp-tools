
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class GenerateComponentVariantsSkill(BaseSkill):
    name = "design.generate_component_variants"
    description = (
        "Generate a component with CVA (class-variance-authority) variants "
        "for consistent, type-safe variant styling."
    )
    category = SkillCategory.DESIGN
    tags = ["variants", "cva", "design-system", "tailwind", "type-safe"]
    parameters = [
        SkillParameter("name", "Component name (e.g. Button, Badge, Card, Alert)"),
        SkillParameter(
            "variants",
            "Variant groups as name:option1|option2 (e.g. variant:default|destructive|outline|ghost, size:sm|md|lg)",
            required=False, default="variant:default|secondary|outline|ghost,size:sm|md|lg",
        ),
        SkillParameter("base_element", "HTML base element", required=False, default="button", enum=["button", "div", "span", "a", "input"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        variants: str = "variant:default|secondary|outline|ghost,size:sm|md|lg",
        base_element: str = "button",
        **_: Any,
    ) -> SkillResult:
        variant_groups: dict[str, list[str]] = {}
        for group in variants.split(","):
            group = group.strip()
            if ":" in group:
                group_name, options_str = group.split(":", 1)
                variant_groups[group_name.strip()] = [o.strip() for o in options_str.split("|")]

        variants_block = ""
        for group_name, options in variant_groups.items():
            variants_block += f"      {group_name}: {{\n"
            for option in options:
                if group_name == "variant":
                    cls_map = {
                        "default": "bg-primary text-primary-foreground hover:bg-primary/90",
                        "secondary": "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                        "outline": "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
                        "ghost": "hover:bg-accent hover:text-accent-foreground",
                        "destructive": "bg-destructive text-destructive-foreground hover:bg-destructive/90",
                        "link": "text-primary underline-offset-4 hover:underline",
                    }
                    classes = cls_map.get(option, "bg-muted text-muted-foreground")
                elif group_name == "size":
                    size_map = {
                        "sm": "h-8 px-3 text-xs",
                        "md": "h-9 px-4 text-sm",
                        "lg": "h-11 px-6 text-base",
                        "icon": "h-9 w-9",
                    }
                    classes = size_map.get(option, "h-9 px-4 text-sm")
                else:
                    classes = ""
                variants_block += f"        {option}: '{classes}',\n"
            variants_block += "      },\n"

        first_variant = next(iter(variant_groups.values()))[0] if variant_groups else "default"
        first_size = variant_groups.get("size", ["md"])[0]

        code = (
            'import { cva, type VariantProps } from "class-variance-authority"\n'
            'import { cn } from "@/lib/utils"\n'
            'import { forwardRef } from "react"\n\n'
            f"const {name.lower()}Variants = cva(\n"
            f"  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50',\n"
            f"  {{\n"
            f"    variants: {{\n"
            f"{variants_block}"
            f"    }},\n"
            f"    defaultVariants: {{\n"
            f"      variant: '{first_variant}',\n"
            f"      size: '{first_size}',\n"
            f"    }},\n"
            f"  }}\n"
            f")\n\n"
            f"export interface {name}Props\n"
            f"  extends React.{base_element.title()}HTMLAttributes<HTML{base_element.title()}Element>,\n"
            f"    VariantProps<typeof {name.lower()}Variants> {{}}\n\n"
            f"export const {name} = forwardRef<HTML{base_element.title()}Element, {name}Props>(\n"
            f"  ({{ className, variant, size, ...props }}, ref) => {{\n"
            f"    return (\n"
            f"      <{base_element}\n"
            f"        ref={{ref}}\n"
            f"        className={{cn({name.lower()}Variants({{ variant, size, className }})}}\n"
            f"        {{...props}}\n"
            f"      />\n"
            f"    )\n"
            f"  }}\n"
            f")\n"
            f"{name}.displayName = '{name}'\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated `{name}` with CVA variants: {list(variant_groups.keys())}",
            artifacts=[CodeArtifact(filename=f"components/ui/{name.lower()}.tsx", content=code, language="tsx")],
            dependencies=["class-variance-authority"],
        )
