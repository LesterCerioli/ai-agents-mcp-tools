
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import DESIGN_EXPERT


@SkillRegistry.register
class ImplementFramerMotionSkill(BaseSkill):
    name = "design.implement_animations"
    description = (
        "Generate animation components using Framer Motion for page transitions, "
        "scroll animations, gesture interactions, and micro-animations."
    )
    category = SkillCategory.DESIGN
    tags = ["animation", "framer-motion", "transitions", "motion", "ux"]
    parameters = [
        SkillParameter(
            "type", "Animation type", enum=[
                "page-transition", "scroll-reveal", "stagger-list",
                "modal-enter", "gesture-card", "loading-skeleton",
                "counter-up", "parallax", "magnetic-button", "confetti",
            ],
        ),
        SkillParameter("target", "Component or element to animate (e.g. ProductCard, PageWrapper, ListItem)"),
        SkillParameter(
            "reduced_motion", "Respect prefers-reduced-motion", required=False, default="true",
            enum=["true", "false"],
        ),
    ]

    async def execute(  # type: ignore[override]
        self,
        type: str,
        target: str,
        reduced_motion: str = "true",
        **_: Any,
    ) -> SkillResult:
        prompt = f"""Generate a Framer Motion animation for `{type}` applied to `{target}`.

{"Include useReducedMotion() hook and skip animations when true" if reduced_motion == "true" else ""}

Requirements:
- Import motion from 'framer-motion'
- TypeScript with proper types
- Smooth, professional animation values (don't be jarring)
- Reusable component or hook pattern
- {"useReducedMotion() for accessibility" if reduced_motion == "true" else ""}
- CSS fallback for users without JS

Animation specifics for {type}:
- page-transition: fade + slide, use AnimatePresence in layout
- scroll-reveal: use whileInView + viewport once:true
- stagger-list: parent + children with staggerChildren
- modal-enter: scale + fade with spring physics
- gesture-card: hover scale + tilt with useMotionValues
- loading-skeleton: shimmer pulse animation
- counter-up: useMotionValue + useTransform for number animation
- parallax: useScroll + useTransform for Y offset
- magnetic-button: mouse tracking with spring
- confetti: particle burst on click

Generate the complete component."""

        if self.llm:
            code = await self.llm.generate_code(prompt, language="tsx", context=DESIGN_EXPERT)
        else:
            animations_map = {
                "page-transition": (
                    '"use client"\n\n'
                    'import { motion } from "framer-motion"\n'
                    'import { useReducedMotion } from "framer-motion"\n\n'
                    'export function PageTransition({ children }: { children: React.ReactNode }) {\n'
                    '  const shouldReduce = useReducedMotion()\n'
                    '  return (\n'
                    '    <motion.div\n'
                    '      initial={shouldReduce ? {} : { opacity: 0, y: 8 }}\n'
                    '      animate={{ opacity: 1, y: 0 }}\n'
                    '      exit={shouldReduce ? {} : { opacity: 0, y: -8 }}\n'
                    '      transition={{ duration: 0.3, ease: "easeInOut" }}\n'
                    '    >\n'
                    '      {children}\n'
                    '    </motion.div>\n'
                    '  )\n'
                    '}\n'
                ),
                "scroll-reveal": (
                    '"use client"\n\n'
                    'import { motion, useReducedMotion } from "framer-motion"\n\n'
                    f'export function ScrollReveal{target}({{ children }}: {{ children: React.ReactNode }}) {{\n'
                    '  const shouldReduce = useReducedMotion()\n'
                    '  return (\n'
                    '    <motion.div\n'
                    '      initial={shouldReduce ? {} : { opacity: 0, y: 24 }}\n'
                    '      whileInView={{ opacity: 1, y: 0 }}\n'
                    '      viewport={{ once: true, margin: "-50px" }}\n'
                    '      transition={{ duration: 0.5, ease: "easeOut" }}\n'
                    '    >\n'
                    '      {children}\n'
                    '    </motion.div>\n'
                    '  )\n'
                    '}\n'
                ),
                "stagger-list": (
                    '"use client"\n\n'
                    'import { motion, useReducedMotion } from "framer-motion"\n\n'
                    'const container = {\n'
                    '  hidden: { opacity: 0 },\n'
                    '  show: { opacity: 1, transition: { staggerChildren: 0.1 } },\n'
                    '}\n'
                    'const item = {\n'
                    '  hidden: { opacity: 0, y: 16 },\n'
                    '  show: { opacity: 1, y: 0 },\n'
                    '}\n\n'
                    f'interface Stagger{target}Props {{\n'
                    '  items: React.ReactNode[]\n'
                    '}\n\n'
                    f'export function Stagger{target}({{ items }}: Stagger{target}Props) {{\n'
                    '  const shouldReduce = useReducedMotion()\n'
                    '  return (\n'
                    '    <motion.ul variants={shouldReduce ? {} : container} initial="hidden" animate="show" className="space-y-2">\n'
                    '      {items.map((child, i) => (\n'
                    '        <motion.li key={i} variants={shouldReduce ? {} : item}>{child}</motion.li>\n'
                    '      ))}\n'
                    '    </motion.ul>\n'
                    '  )\n'
                    '}\n'
                ),
            }
            code = animations_map.get(type, animations_map["scroll-reveal"])

        return SkillResult(
            success=True,
            summary=f"Generated `{type}` animation for `{target}`",
            artifacts=[CodeArtifact(
                filename=f"components/animations/{type.replace('-', '_')}.tsx",
                content=code, language="tsx",
            )],
            dependencies=["framer-motion"],
        )


@SkillRegistry.register
class GenerateLoadingUISkill(BaseSkill):
    name = "design.generate_loading_ui"
    description = (
        "Generate skeleton loading screens and loading state components "
        "that match specific UI patterns for better perceived performance."
    )
    category = SkillCategory.DESIGN
    tags = ["loading", "skeleton", "ux", "performance", "placeholder"]
    parameters = [
        SkillParameter("component", "Component to create a skeleton for (e.g. UserCard, ProductList, BlogPost, Dashboard)"),
        SkillParameter(
            "style", "Skeleton animation style", required=False, default="pulse",
            enum=["pulse", "shimmer", "wave", "static"],
        ),
        SkillParameter("count", "Number of skeleton items to show", required=False, default="3"),
    ]

    async def execute(  # type: ignore[override]
        self,
        component: str,
        style: str = "pulse",
        count: str = "3",
        **_: Any,
    ) -> SkillResult:
        animation_class = {
            "pulse": "animate-pulse",
            "shimmer": "animate-pulse [background:linear-gradient(90deg,transparent,rgba(255,255,255,0.4),transparent)] bg-[length:200%_100%]",
            "wave": "animate-pulse",
            "static": "",
        }.get(style, "animate-pulse")

        code = (
            f"import {{ Skeleton }} from '@/components/ui/skeleton'\n\n"
            f"export function {component}Skeleton() {{\n"
            f"  return (\n"
            f"    <div className=\"{animation_class} space-y-3 rounded-xl border bg-card p-4\">\n"
            f"      <div className=\"flex items-center space-x-3\">\n"
            f"        <Skeleton className=\"h-10 w-10 rounded-full\" />\n"
            f"        <div className=\"space-y-2 flex-1\">\n"
            f"          <Skeleton className=\"h-4 w-32\" />\n"
            f"          <Skeleton className=\"h-3 w-24\" />\n"
            f"        </div>\n"
            f"      </div>\n"
            f"      <Skeleton className=\"h-4 w-full\" />\n"
            f"      <Skeleton className=\"h-4 w-5/6\" />\n"
            f"      <Skeleton className=\"h-4 w-4/6\" />\n"
            f"    </div>\n"
            f"  )\n"
            f"}}\n\n"
            f"export function {component}ListSkeleton({{ count = {count} }}: {{ count?: number }}) {{\n"
            f"  return (\n"
            f"    <div className=\"space-y-4\" aria-busy=\"true\" aria-label=\"Loading {component.lower()}s\">\n"
            f"      {{Array.from({{ length: count }}).map((_, i) => (\n"
            f"        <{component}Skeleton key={{i}} />\n"
            f"      ))}}\n"
            f"    </div>\n"
            f"  )\n"
            f"}}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated {style} skeleton for `{component}`",
            artifacts=[CodeArtifact(
                filename=f"components/{component}Skeleton.tsx", content=code, language="tsx",
            )],
            instructions=["npx shadcn@latest add skeleton"],
        )
