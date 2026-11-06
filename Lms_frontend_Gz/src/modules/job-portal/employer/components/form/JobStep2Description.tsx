import { useState } from "react";
import { Icon, Button } from "@/shared/ui";
import { cn } from "@/core/lib/cn";
import type { JobFormValues } from "@/modules/job-portal/employer/form/jobForm";
import { BulletListEditor } from "./BulletListEditor";
import { RichTextEditor } from "./RichTextEditor";

interface Props {
  values: JobFormValues;
  set: <K extends keyof JobFormValues>(key: K, value: JobFormValues[K]) => void;
  locked: boolean;
  errors?: Record<string, string>;
}

const TEMPLATES: Record<
  string,
  {
    name: string;
    about: string;
    minQuals: string[];
    prefQuals: string[];
    responsibilities: string[];
    perks: string[];
    level: "fresher" | "junior" | "mid" | "senior" | "lead";
    levelDesc: string;
  }
> = {
  software_developer: {
    name: "Software Developer",
    about:
      "We are seeking a passionate Software Developer to design, build, and maintain high-performance software applications. You will collaborate closely with cross-functional engineering teams to deliver robust, scalable solutions.",
    minQuals: [
      "Bachelor's degree in Computer Science, Engineering, or equivalent practical experience",
      "Proficiency in at least one modern language (Python, Java, TypeScript, or Go)",
      "Strong understanding of data structures, algorithms, and software design principles",
    ],
    prefQuals: [
      "Experience with cloud infrastructure (AWS, GCP, or Azure)",
      "Familiarity with containerization (Docker, Kubernetes) and CI/CD pipelines",
    ],
    responsibilities: [
      "Write clean, maintainable, and thoroughly tested production code",
      "Participate actively in architectural discussions and code reviews",
      "Troubleshoot, debug, and optimize application performance and reliability",
    ],
    perks: [
      "Flexible hybrid working model and remote work allowance",
      "Comprehensive medical, dental, and vision insurance",
      "Annual continuous learning stipend and conference budget",
    ],
    level: "junior",
    levelDesc: "1-3 years of relevant experience in software development.",
  },
  data_analyst: {
    name: "Data Analyst",
    about:
      "Join our data team as a Data Analyst to transform complex datasets into actionable business insights. You will work with stakeholders across the organization to drive informed, data-driven decisions.",
    minQuals: [
      "Bachelor's degree in Mathematics, Statistics, Computer Science, or Economics",
      "Strong proficiency in SQL querying and relational databases",
      "Demonstrated experience with BI tools (Tableau, PowerBI, or Metabase)",
    ],
    prefQuals: [
      "Hands-on experience with Python or R for statistical data analysis",
      "Knowledge of data warehousing and modern ETL pipelines",
    ],
    responsibilities: [
      "Extract, clean, and validate data across enterprise business systems",
      "Design, build, and maintain automated dashboards and executive reports",
      "Identify emerging trends and communicate predictive recommendations to leadership",
    ],
    perks: [
      "Competitive compensation package with annual performance bonus",
      "Comprehensive health coverage and wellness allowances",
      "Dedicated weekly focus hours for learning and certifications",
    ],
    level: "mid",
    levelDesc: "2-4 years of experience delivering quantitative analytics.",
  },
  ai_ml_intern: {
    name: "AI/ML Intern",
    about:
      "We are looking for an ambitious AI/ML Intern to contribute to cutting-edge machine learning models and intelligent AI features across our platform.",
    minQuals: [
      "Currently pursuing or recent graduate in Computer Science, Artificial Intelligence, or Data Science",
      "Proficiency in Python and ML frameworks (PyTorch, TensorFlow, or Scikit-Learn)",
      "Solid foundation in linear algebra, calculus, and probability",
    ],
    prefQuals: [
      "Experience with Natural Language Processing (NLP) or Large Language Models (LLMs)",
      "Contributions to open-source ML repositories or Kaggle competitions",
    ],
    responsibilities: [
      "Assist in training, evaluating, and fine-tuning machine learning models",
      "Preprocess, clean, and curate benchmark datasets for model evaluation",
      "Document experimental outcomes and benchmark inference latencies",
    ],
    perks: [
      "Direct 1-on-1 mentorship from experienced senior AI researchers",
      "Access to modern GPU computing infrastructure for experiments",
      "Certificate of internship completion with high potential for full-time offer",
    ],
    level: "fresher",
    levelDesc: "0-1 years of experience, suitable for students and fresh graduates.",
  },
  frontend_intern: {
    name: "Frontend Intern",
    about:
      "Exciting opportunity for a Frontend Intern to craft intuitive, accessible, and responsive web user interfaces used by thousands of learners daily.",
    minQuals: [
      "Pursuing a degree in Computer Science, Design, or self-taught developer",
      "Solid understanding of HTML5, CSS3, modern JavaScript (ES6+), and React",
      "Strong eye for visual design details and responsive layout principles",
    ],
    prefQuals: [
      "Familiarity with TypeScript, Tailwind CSS, and REST API integration",
      "Portfolio or active GitHub profile showcasing interactive frontend projects",
    ],
    responsibilities: [
      "Implement pixel-perfect UI components following design system specifications",
      "Ensure seamless responsiveness and accessibility across desktop and mobile browsers",
      "Collaborate with backend engineers to consume RESTful APIs",
    ],
    perks: [
      "Hands-on mentorship from senior frontend staff engineers",
      "Flexible schedule accommodating academic courses and exams",
      "Fast-track conversion path to a junior engineering position",
    ],
    level: "fresher",
    levelDesc: "Entry-level role, ideal for students and early-career developers.",
  },
  qa_testing: {
    name: "QA / Testing",
    about:
      "We are looking for a QA / Test Engineer to uphold product reliability and elevate user satisfaction through rigorous automated and exploratory testing.",
    minQuals: [
      "Bachelor's degree in Computer Science, Information Technology, or equivalent",
      "Strong understanding of QA methodologies, test life cycles, and bug tracking",
      "Experience writing detailed test plans, test matrices, and defect reports",
    ],
    prefQuals: [
      "Experience with browser automation tools (Playwright, Cypress, or Selenium)",
      "API testing experience using Postman or automated test scripts",
    ],
    responsibilities: [
      "Design and execute test strategies for new features across releases",
      "Develop and maintain automated regression and smoke test suites",
      "Partner with development teams to triage, isolate, and verify bug fixes",
    ],
    perks: [
      "Competitive salary with performance incentives",
      "Full medical and personal wellness benefits",
      "Support for professional testing certifications (ISTQB, etc.)",
    ],
    level: "junior",
    levelDesc: "1-3 years in software quality assurance and test automation.",
  },
};

export function JobStep2Description({ values, set, locked, errors = {} }: Props) {
  const [selectedTemplate, setSelectedTemplate] = useState<string>("");
  const [confirmOverwrite, setConfirmOverwrite] = useState<string | null>(null);
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [aiDraft, setAiDraft] = useState<{
    about: string;
    minQuals: string[];
    responsibilities: string[];
  } | null>(null);

  const applyTemplate = (key: string) => {
    if (key === "blank") {
      set("about_job", "");
      set("minimum_qualifications", []);
      set("preferred_qualifications", []);
      set("responsibilities", []);
      set("perks", []);
      setConfirmOverwrite(null);
      setSelectedTemplate("");
      return;
    }

    const t = TEMPLATES[key];
    if (!t) return;

    set("about_job", t.about);
    set("minimum_qualifications", t.minQuals);
    set("preferred_qualifications", t.prefQuals);
    set("responsibilities", t.responsibilities);
    set("perks", t.perks);
    set("experience_level", t.level);
    set("experience_level_description", t.levelDesc);
    setConfirmOverwrite(null);
    setSelectedTemplate(key);
  };

  const handleTemplateSelect = (key: string) => {
    if (!key) return;
    const hasData =
      Boolean((values.about_job || "").trim()) ||
      (values.minimum_qualifications || []).length > 0 ||
      (values.responsibilities || []).length > 0;

    if (hasData) {
      setConfirmOverwrite(key);
    } else {
      applyTemplate(key);
    }
  };

  const handleAiAssist = () => {
    setAiGenerating(true);
    setTimeout(() => {
      const title = (values.title || "").trim() || "Software Engineer";
      const skills = values.required_skills
        ? values.required_skills.split(",").map((s) => s.trim()).filter(Boolean)
        : ["Core Technical Skills"];

      const generated = {
        about: `We are hiring a dedicated ${title} to join our growing engineering organization. In this role, you will leverage your expertise in ${skills.slice(0, 3).join(", ")} to architect scalable products and solve mission-critical problems for our users.`,
        minQuals: [
          `Bachelor's degree in Computer Science, Engineering, or equivalent practical experience`,
          `Demonstrated proficiency and hands-on production experience in ${skills.slice(0, 2).join(" and ")}`,
          `Strong understanding of modern system design, testing methodologies, and problem solving`,
        ],
        responsibilities: [
          `Design, develop, and maintain high-quality backend services and APIs`,
          `Collaborate with product managers and peers to deliver scalable features`,
          `Drive performance optimization, test coverage, and documentation`,
        ],
      };
      setAiDraft(generated);
      setAiGenerating(false);
      setAiModalOpen(true);
    }, 600);
  };

  const applyAiDraft = () => {
    if (!aiDraft) return;
    set("about_job", aiDraft.about);
    set("minimum_qualifications", aiDraft.minQuals);
    set("responsibilities", aiDraft.responsibilities);
    setAiModalOpen(false);
  };

  const experienceLevels = [
    { value: "fresher", label: "Fresher", subtitle: "0-1 years" },
    { value: "junior", label: "Junior", subtitle: "1-3 years" },
    { value: "mid", label: "Mid-level", subtitle: "3-5 years" },
    { value: "senior", label: "Senior", subtitle: "5-8 years" },
    { value: "lead", label: "Lead", subtitle: "8+ years" },
  ];

  const bannerTextTrimmed = (values.banner_text || "").trim();

  return (
    <div className="space-y-7">
      {/* 1. Header Tools Bar (Template Picker & AI Assist) */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 rounded-xl border border-emerald-200/90 bg-emerald-50/40">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-emerald-600 text-white shadow-sm">
            <Icon name="sparkles" className="h-4 w-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-emerald-950">Role Description Tools</h4>
            <p className="text-[11px] text-slate-500">
              Pick a pre-filled role template or generate standard requirements
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-slate-600 font-medium">Use template:</span>
            <select
              value={selectedTemplate}
              disabled={locked}
              onChange={(e) => handleTemplateSelect(e.target.value)}
              className="text-xs font-semibold border border-slate-300 rounded-lg bg-white px-2.5 py-1.5 text-slate-800 focus:outline-none focus:ring-1 focus:ring-emerald-500 shadow-sm"
            >
              <option value="">Select template...</option>
              <option value="software_developer">Software Developer</option>
              <option value="data_analyst">Data Analyst</option>
              <option value="ai_ml_intern">AI/ML Intern</option>
              <option value="frontend_intern">Frontend Intern</option>
              <option value="qa_testing">QA / Testing</option>
              <option value="blank">Blank (Clear all fields)</option>
            </select>
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={handleAiAssist}
            loading={aiGenerating}
            disabled={locked}
            className="text-xs gap-1.5 border-emerald-300 text-emerald-800 hover:bg-emerald-100/60 font-semibold"
          >
            <Icon name="sparkles" className="h-3.5 w-3.5 text-emerald-600" />
            AI Assist
          </Button>
        </div>
      </div>

      {/* Confirmation Modal for Template Overwrite */}
      {confirmOverwrite && (
        <div className="p-4 rounded-xl border border-amber-300 bg-amber-50/95 text-amber-900 space-y-3">
          <div className="flex items-start gap-2.5">
            <Icon name="alert-triangle" className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <h5 className="text-xs font-bold">Replace existing Job Description content?</h5>
              <p className="text-xs text-amber-800 mt-0.5">
                Applying the <strong>{confirmOverwrite === "blank" ? "Blank" : TEMPLATES[confirmOverwrite]?.name}</strong> template
                will overwrite text currently entered in Minimum qualifications, Preferred qualifications,
                About the job, Responsibilities, and Perks.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={() => {
                setConfirmOverwrite(null);
                setSelectedTemplate("");
              }}
              className="px-3 py-1 text-xs font-semibold rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => applyTemplate(confirmOverwrite)}
              className="px-3 py-1 text-xs font-semibold rounded-lg bg-amber-600 text-white hover:bg-amber-700"
            >
              Confirm Overwrite
            </button>
          </div>
        </div>
      )}

      {/* AI Draft Modal */}
      {aiModalOpen && aiDraft && (
        <div className="p-4 rounded-xl border border-emerald-300 bg-emerald-50 text-emerald-950 space-y-3">
          <div className="flex items-center justify-between border-b border-emerald-200 pb-2">
            <div className="flex items-center gap-2">
              <Icon name="sparkles" className="h-4 w-4 text-emerald-700" />
              <h5 className="text-xs font-bold">Generated AI Draft for Review</h5>
            </div>
            <button
              type="button"
              onClick={() => setAiModalOpen(false)}
              className="text-xs text-slate-500 hover:text-slate-800"
            >
              Close
            </button>
          </div>
          <div className="space-y-2 text-xs">
            <div>
              <span className="font-bold text-emerald-900">About the job:</span>
              <p className="text-slate-700 mt-0.5 italic">{aiDraft.about}</p>
            </div>
            <div>
              <span className="font-bold text-emerald-900">Minimum qualifications:</span>
              <ul className="list-disc pl-5 space-y-0.5 text-slate-700 mt-0.5">
                {aiDraft.minQuals.map((q, i) => (
                  <li key={i}>{q}</li>
                ))}
              </ul>
            </div>
            <div>
              <span className="font-bold text-emerald-900">Responsibilities:</span>
              <ul className="list-disc pl-5 space-y-0.5 text-slate-700 mt-0.5">
                {aiDraft.responsibilities.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2 pt-2 border-t border-emerald-200">
            <button
              type="button"
              onClick={() => setAiModalOpen(false)}
              className="px-3 py-1 text-xs font-medium rounded-lg border border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            >
              Discard
            </button>
            <button
              type="button"
              onClick={applyAiDraft}
              className="px-3 py-1 text-xs font-bold rounded-lg bg-emerald-600 text-white hover:bg-emerald-700"
            >
              Insert into Form
            </button>
          </div>
        </div>
      )}

      {/* 2. Info Banner (Optional) */}
      <div className="space-y-2 scroll-mt-24" id="field-banner">
        <label className="text-xs font-semibold text-slate-800 flex items-center justify-between">
          <span>Info Notice Banner (Optional)</span>
          <span className="text-[11px] text-slate-400 font-normal">Highlighted banner notice shown at the top of the job post</span>
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-2.5">
          <div className="sm:col-span-3">
            <input
              type="text"
              value={values.banner_text || ""}
              disabled={locked}
              placeholder='e.g., "Applications close on 27 Dec" or "Urgent requirement with immediate joining"'
              maxLength={160}
              onChange={(e) => set("banner_text", e.target.value)}
              className="w-full h-10 px-3 text-xs rounded-xl border border-slate-300 text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            />
          </div>
          <div>
            <select
              value={values.banner_type || "info"}
              disabled={locked}
              onChange={(e) => set("banner_type", e.target.value as "info" | "warning")}
              className="w-full h-10 text-xs font-medium rounded-xl border border-slate-300 bg-white px-3 text-slate-800 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
            >
              <option value="info">Info Notice (Blue)</option>
              <option value="warning">Warning Notice (Amber)</option>
            </select>
          </div>
        </div>

        {/* Live Banner Preview */}
        {bannerTextTrimmed && (
          <div
            className={cn(
              "flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-medium border mt-1",
              values.banner_type === "warning"
                ? "bg-amber-50 text-amber-900 border-amber-200"
                : "bg-sky-50 text-sky-900 border-sky-200"
            )}
          >
            <Icon
              name={values.banner_type === "warning" ? "alert-triangle" : "info"}
              className="h-4 w-4 shrink-0"
            />
            <span>{bannerTextTrimmed}</span>
          </div>
        )}
      </div>

      {/* 3. Experience Level (Segmented chips + description input) */}
      <div className="space-y-2.5 scroll-mt-24" id="field-experience_level">
        <label className="text-xs font-semibold text-slate-800 flex items-center justify-between">
          <span className="flex items-center gap-1">
            <span>Experience Level</span>
            <span className="text-rose-500 font-bold">*</span>
          </span>
          <span className="text-[11px] text-slate-400 font-normal">Shown as a tag with tooltip</span>
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {experienceLevels.map((lvl) => {
            const isSelected = (values.experience_level || "fresher") === lvl.value;
            return (
              <button
                key={lvl.value}
                type="button"
                disabled={locked}
                onClick={() => set("experience_level", lvl.value as any)}
                className={cn(
                  "p-2.5 rounded-xl text-left border transition-all flex flex-col justify-center",
                  isSelected
                    ? "bg-emerald-50 border-emerald-600 ring-2 ring-emerald-600/20 shadow-sm"
                    : "bg-white border-slate-300 hover:border-slate-400 hover:bg-slate-50"
                )}
              >
                <span className={cn("text-xs font-bold leading-tight", isSelected ? "text-emerald-900" : "text-slate-800")}>
                  {lvl.label}
                </span>
                <span className="text-[10px] text-slate-500">{lvl.subtitle}</span>
              </button>
            );
          })}
        </div>

        <input
          type="text"
          value={values.experience_level_description || ""}
          disabled={locked}
          placeholder="Tooltip description, e.g., '0-1 years of experience, suitable for fresh graduates'"
          maxLength={200}
          onChange={(e) => set("experience_level_description", e.target.value)}
          className="w-full h-9 px-3 text-xs rounded-xl border border-slate-200 text-slate-700 placeholder:text-slate-400 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-500"
        />
      </div>

      {/* 4. About the job (Rich Text Editor) */}
      <div id="field-about_job" className="scroll-mt-24">
        <RichTextEditor
          label="About the Job"
          value={values.about_job || ""}
          onChange={(val) => set("about_job", val)}
          disabled={locked}
          required
          minCharacters={10}
          placeholder="Describe the company mission, what the candidate will work on, and why this position is exciting..."
        />
        {errors.about_job && <p className="text-xs text-rose-600 font-medium mt-1">{errors.about_job}</p>}
      </div>

      {/* 5. Minimum Qualifications (Bullet-list, required min 2, NO description) */}
      <div id="field-minimum_qualifications" className="scroll-mt-24">
        <BulletListEditor
          label="Minimum Qualifications"
          items={values.minimum_qualifications || []}
          onChange={(items) => set("minimum_qualifications", items)}
          required
          minItems={2}
          placeholder="e.g., Bachelor's degree in Computer Science or 2+ years of experience in Python"
        />
        {errors.minimum_qualifications && (
          <p className="text-xs text-rose-600 font-medium mt-1">{errors.minimum_qualifications}</p>
        )}
      </div>

      {/* 6. Preferred Qualifications (Bullet-list, optional, NO description) */}
      <div id="field-preferred_qualifications" className="scroll-mt-24">
        <BulletListEditor
          label="Preferred Qualifications (Optional)"
          items={values.preferred_qualifications || []}
          onChange={(items) => set("preferred_qualifications", items)}
          placeholder="e.g., Hands-on experience with Docker, Kubernetes, or AWS cloud deployments"
        />
      </div>

      {/* 7. Responsibilities (Bullet-list, required min 3, NO description) */}
      <div id="field-responsibilities" className="scroll-mt-24">
        <BulletListEditor
          label="Responsibilities"
          items={values.responsibilities || []}
          onChange={(items) => set("responsibilities", items)}
          required
          minItems={3}
          placeholder="e.g., Architect, implement, and maintain scalable REST APIs and backend microservices"
        />
        {errors.responsibilities && (
          <p className="text-xs text-rose-600 font-medium mt-1">{errors.responsibilities}</p>
        )}
      </div>

      {/* 8. Perks & Benefits (Bullet-list, optional, NO description) */}
      <div id="field-perks" className="scroll-mt-24">
        <BulletListEditor
          label="Perks & Benefits (Optional)"
          items={values.perks || []}
          onChange={(items) => set("perks", items)}
          placeholder="e.g., Comprehensive health insurance, remote work allowance, annual learning stipend"
        />
      </div>
    </div>
  );
}
