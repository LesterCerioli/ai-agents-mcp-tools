
from typing import Any
from ..base import BaseSkill, SkillCategory, SkillParameter, SkillResult, CodeArtifact
from ..registry import SkillRegistry
from app.llm.prompts import FRONTEND_EXPERT


@SkillRegistry.register
class GenerateZodSchemaSkill(BaseSkill):
    name = "frontend.generate_zod_schema"
    description = (
        "Generate a comprehensive Zod schema with custom validators, "
        "refinements, transformations, and TypeScript inference types."
    )
    category = SkillCategory.FRONTEND
    tags = ["zod", "validation", "schema", "typescript"]
    parameters = [
        SkillParameter("name", "Schema name (e.g. LoginSchema, CreateProductSchema, ProfileSchema)"),
        SkillParameter(
            "fields",
            "Comma-separated field definitions (e.g. email:email, password:min8, name:min2|max50, age:number|min18, role:enum:admin|user|guest)",
        ),
        SkillParameter("purpose", "What this schema validates (e.g. user login, product creation, profile update)", required=False, default=""),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        fields: str,
        purpose: str = "",
        **_: Any,
    ) -> SkillResult:
        field_list = [f.strip() for f in fields.split(",") if f.strip()]

        field_definitions = []
        for field in field_list:
            parts = field.split(":")
            field_name = parts[0].strip()
            field_type = parts[1].strip() if len(parts) > 1 else "string"
            constraints = parts[2].strip() if len(parts) > 2 else ""

            if field_type == "email":
                zod_def = "z.string().email('Invalid email address').toLowerCase()"
            elif field_type == "password":
                zod_def = "z.string().min(8, 'Password must be at least 8 characters').max(128)"
            elif field_type == "url":
                zod_def = "z.string().url('Must be a valid URL')"
            elif field_type == "number":
                min_val = next((c.replace("min", "") for c in constraints.split("|") if c.startswith("min")), None)
                max_val = next((c.replace("max", "") for c in constraints.split("|") if c.startswith("max")), None)
                zod_def = "z.number()"
                if min_val:
                    zod_def += f".min({min_val})"
                if max_val:
                    zod_def += f".max({max_val})"
            elif field_type == "enum":
                enum_values = constraints.split("|") if constraints else ["option1", "option2"]
                enum_str = ", ".join(f"'{v}'" for v in enum_values)
                zod_def = f"z.enum([{enum_str}])"
            elif field_type == "boolean":
                zod_def = "z.boolean()"
            elif field_type == "date":
                zod_def = "z.coerce.date()"
            elif field_type == "file":
                zod_def = "z.instanceof(File).refine(f => f.size < 5_000_000, 'File must be smaller than 5MB')"
            else:
                min_val = next((c.replace("min", "") for c in field_type.split("|") if c.startswith("min")), None)
                max_val = next((c.replace("max", "") for c in field_type.split("|") if c.startswith("max")), None)
                zod_def = "z.string()"
                if min_val:
                    zod_def += f".min({min_val}, 'Must be at least {min_val} characters')"
                if max_val:
                    zod_def += f".max({max_val}, 'Must not exceed {max_val} characters')"

            optional = "optional" in constraints or "?" in field_name
            if optional:
                zod_def += ".optional()"
                field_name = field_name.rstrip("?")

            field_definitions.append(f"  {field_name}: {zod_def},")

        code = (
            f"import {{ z }} from 'zod'\n\n"
            f"export const {name} = z.object({{\n"
            + "\n".join(field_definitions)
            + "\n})"
        )

        # Add password confirmation refinement if both password fields exist
        field_names = [f.split(":")[0].strip() for f in field_list]
        if "password" in field_names and "confirmPassword" in field_names:
            code += (
                "\n.refine(\n"
                "  (data) => data.password === data.confirmPassword,\n"
                "  {\n"
                "    message: 'Passwords do not match',\n"
                "    path: ['confirmPassword'],\n"
                "  }\n"
                ")"
            )

        code += f"\n\nexport type {name.replace('Schema', '')}Data = z.infer<typeof {name}>\n"

        return SkillResult(
            success=True,
            summary=f"Generated Zod schema `{name}` with {len(field_list)} fields",
            artifacts=[CodeArtifact(filename=f"schemas/{name.lower().replace('schema', '')}.ts", content=code, language="typescript")],
            dependencies=["zod"],
        )


@SkillRegistry.register
class GenerateMultiStepFormSkill(BaseSkill):
    name = "frontend.generate_multi_step_form"
    description = (
        "Generate a multi-step wizard form with progress indicator, "
        "step validation, navigation, and final submission."
    )
    category = SkillCategory.FRONTEND
    tags = ["form", "multi-step", "wizard", "react-hook-form", "zod"]
    parameters = [
        SkillParameter("name", "Form name (e.g. OnboardingWizard, CheckoutForm, RegistrationFlow)"),
        SkillParameter(
            "steps",
            "Comma-separated step definitions (e.g. Personal Info:name|email, Account:username|password, Preferences:role|newsletter)",
        ),
        SkillParameter("on_complete", "What happens on final submit (e.g. create account, place order)", required=False, default="submit form data"),
    ]

    async def execute(  # type: ignore[override]
        self,
        name: str,
        steps: str,
        on_complete: str = "submit form data",
        **_: Any,
    ) -> SkillResult:
        step_list = []
        for step in steps.split(","):
            step = step.strip()
            if ":" in step:
                step_name, fields_str = step.split(":", 1)
                step_list.append({
                    "name": step_name.strip(),
                    "fields": [f.strip() for f in fields_str.split("|") if f.strip()],
                })

        step_lines = []
        for i, s in enumerate(step_list):
            fields_repr = ", ".join(repr(f) for f in s["fields"])
            step_lines.append(f"  {{ id: '{i + 1}', title: '{s['name']}', fields: [{fields_repr}] }},")
        steps_const = "[\n" + "\n".join(step_lines) + "\n]"

        code = (
            '"use client"\n\n'
            "import { useState } from 'react'\n"
            "import { useForm } from 'react-hook-form'\n"
            "import { zodResolver } from '@hookform/resolvers/zod'\n"
            "import { z } from 'zod'\n"
            "import { Button } from '@/components/ui/button'\n"
            "import { Progress } from '@/components/ui/progress'\n\n"
            f"const steps = {steps_const}\n\n"
            f"export function {name}() {{\n"
            "  const [currentStep, setCurrentStep] = useState(0)\n"
            "  const [formData, setFormData] = useState({})\n\n"
            "  const progress = ((currentStep + 1) / steps.length) * 100\n"
            "  const step = steps[currentStep]\n"
            "  const isLast = currentStep === steps.length - 1\n\n"
            "  function handleNext(data: Record<string, unknown>) {\n"
            "    setFormData(prev => ({ ...prev, ...data }))\n"
            "    if (isLast) {\n"
            "      console.log('Submit:', { ...formData, ...data })\n"
            "      return\n"
            "    }\n"
            "    setCurrentStep(s => s + 1)\n"
            "  }\n\n"
            "  return (\n"
            "    <div className=\"mx-auto max-w-lg space-y-6\">\n"
            "      {/* Progress */}\n"
            "      <div className=\"space-y-2\">\n"
            "        <div className=\"flex justify-between text-sm text-muted-foreground\">\n"
            "          <span>Step {currentStep + 1} of {steps.length}</span>\n"
            "          <span>{step.title}</span>\n"
            "        </div>\n"
            "        <Progress value={progress} />\n"
            "      </div>\n\n"
            "      {/* Step content rendered here based on currentStep */}\n"
            "      <div className=\"rounded-lg border bg-card p-6\">\n"
            "        <h2 className=\"mb-4 text-xl font-semibold\">{step.title}</h2>\n"
            "        {/* Render step-specific form fields */}\n"
            "      </div>\n\n"
            "      {/* Navigation */}\n"
            "      <div className=\"flex justify-between\">\n"
            "        <Button variant=\"outline\" onClick={() => setCurrentStep(s => s - 1)} disabled={currentStep === 0}>\n"
            "          Back\n"
            "        </Button>\n"
            "        <Button onClick={() => handleNext({})}>\n"
            "          {isLast ? 'Complete' : 'Next'}\n"
            "        </Button>\n"
            "      </div>\n"
            "    </div>\n"
            "  )\n"
            "}\n"
        )

        return SkillResult(
            success=True,
            summary=f"Generated {len(step_list)}-step wizard form `{name}`",
            artifacts=[CodeArtifact(filename=f"components/{name}.tsx", content=code, language="tsx")],
            dependencies=["react-hook-form", "@hookform/resolvers", "zod"],
            instructions=["npx shadcn@latest add progress form input"],
        )
