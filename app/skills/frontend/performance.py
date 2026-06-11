
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry


@SkillRegistry.register
class ImplementVirtualizationSkill(BaseSkill):
    name = "frontend.implement_virtualization"
    description = "Implement list virtualization with TanStack Virtual for rendering large datasets efficiently."
    category = SkillCategory.FRONTEND
    tags = ["performance", "virtualization", "tanstack-virtual", "large-lists"]
    parameters = [
        SkillParameter("component_name", "Component name (e.g. VirtualProductList, InfiniteMessageList)"),
        SkillParameter("item_height", "Approximate item height in pixels", required=False, default="80"),
        SkillParameter("direction", "Scroll direction", required=False, default="vertical", enum=["vertical", "horizontal"]),
    ]

    async def execute(  # type: ignore[override]
        self,
        component_name: str,
        item_height: str = "80",
        direction: str = "vertical",
        **_: Any,
    ) -> SkillResult:
        code = (
            '"use client"\n\n'
            "import { useRef } from 'react'\n"
            "import { useVirtualizer } from '@tanstack/react-virtual'\n\n"
            "interface ItemProps {\n"
            "  index: number\n"
            "  data: unknown\n"
            "}\n\n"
            f"interface {component_name}Props {{\n"
            "  items: unknown[]\n"
            "  renderItem: (props: ItemProps) => React.ReactNode\n"
            "  className?: string\n"
            "}\n\n"
            f"export function {component_name}({{ items, renderItem, className }}: {component_name}Props) {{\n"
            "  const parentRef = useRef<HTMLDivElement>(null)\n\n"
            "  const virtualizer = useVirtualizer({\n"
            "    count: items.length,\n"
            "    getScrollElement: () => parentRef.current,\n"
            f"    estimateSize: () => {item_height},\n"
            "    overscan: 5,\n"
            "  })\n\n"
            "  return (\n"
            "    <div\n"
            "      ref={parentRef}\n"
            f"      className={{`overflow-{'y' if direction == 'vertical' else 'x'}-auto ${{className}}`}}\n"
            "      style={{ height: '600px' }}\n"
            "    >\n"
            "      <div style={{ height: `${virtualizer.getTotalSize()}px`, position: 'relative' }}>\n"
            "        {virtualizer.getVirtualItems().map(virtualItem => (\n"
            "          <div\n"
            "            key={virtualItem.key}\n"
            "            style={{\n"
            "              position: 'absolute',\n"
            "              top: 0,\n"
            "              left: 0,\n"
            "              width: '100%',\n"
            "              height: `${virtualItem.size}px`,\n"
            "              transform: `translateY(${virtualItem.start}px)`,\n"
            "            }}\n"
            "          >\n"
            "            {renderItem({ index: virtualItem.index, data: items[virtualItem.index] })}\n"
            "          </div>\n"
            "        ))}\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated virtualized list `{component_name}`",
            artifacts=[CodeArtifact(filename=f"components/{component_name}.tsx", content=code, language="tsx")],
            dependencies=["@tanstack/react-virtual"],
        )


@SkillRegistry.register
class ImplementMemoizationSkill(BaseSkill):
    name = "frontend.implement_memoization"
    description = "Analyze and apply React memoization (memo, useMemo, useCallback) to prevent unnecessary re-renders."
    category = SkillCategory.FRONTEND
    tags = ["performance", "memoization", "react.memo", "useMemo", "useCallback"]
    parameters = [
        SkillParameter("component_code", "Component code to analyze and optimize"),
        SkillParameter("optimization_goal", "What to optimize (e.g. expensive calculation, child re-renders, event handlers)", required=False, default="prevent re-renders"),
    ]

    async def execute(  # type: ignore[override]
        self,
        component_code: str,
        optimization_goal: str = "prevent re-renders",
        **_: Any,
    ) -> SkillResult:
        guide = (
            "// Memoization patterns for React performance:\n\n"
            "// 1. React.memo — wrap component to skip re-render if props unchanged\n"
            "const MemoizedComponent = memo(function Component({ value, onAction }) {\n"
            "  return <div>{value}</div>\n"
            "}, (prevProps, nextProps) => {\n"
            "  // Custom comparison — return true to SKIP re-render\n"
            "  return prevProps.value === nextProps.value\n"
            "})\n\n"
            "// 2. useMemo — memoize expensive calculations\n"
            "const expensiveResult = useMemo(() => {\n"
            "  return items.filter(item => item.active).sort((a, b) => b.score - a.score)\n"
            "}, [items]) // Only recalculate when `items` changes\n\n"
            "// 3. useCallback — stable reference for event handlers\n"
            "const handleClick = useCallback((id: string) => {\n"
            "  setState(prev => prev.filter(item => item.id !== id))\n"
            "}, []) // Empty deps = created once, stable forever\n\n"
            "// 4. When NOT to memoize:\n"
            "// - Simple primitives (strings, booleans, numbers)\n"
            "// - Fast calculations\n"
            "// - Components that always need to re-render\n"
            "// - When deps change as often as re-renders\n\n"
            "// 5. useRef for stable non-rendering values\n"
            "const timeoutRef = useRef<ReturnType<typeof setTimeout>>()\n"
        )

        return SkillResult(
            success=True,
            summary=f"Memoization guide for: {optimization_goal}",
            artifacts=[CodeArtifact(filename="guides/memoization-patterns.tsx", content=guide, language="tsx")],
            next_steps=[
                "Install React DevTools and use Profiler to identify re-renders",
                "Use why-did-you-render library to trace unnecessary renders",
                "Only optimize after measuring — premature optimization adds complexity",
            ],
        )
