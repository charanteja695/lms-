import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Icon } from "@/shared/ui";

interface JobPosting {
  id: string;
  title: string;
  company: string;
  companyInitials: string;
  companyColor: string;
  matchScore?: number;
  isInternship?: boolean;
  salary: string;
  location: string;
  type: string;
  tags: string[];
}

const JOBS: JobPosting[] = [
  {
    id: "1",
    title: "Python Developer",
    company: "TechCorp Solutions",
    companyInitials: "TC",
    companyColor: "bg-blue-50 text-[#635BFF]",
    matchScore: 92,
    salary: "₹ 8 – 12 LPA",
    location: "Bengaluru",
    type: "Full-time",
    tags: ["Python", "Django", "REST APIs"],
  },
  {
    id: "2",
    title: "Data Scientist",
    company: "DataVision Labs",
    companyInitials: "DV",
    companyColor: "bg-emerald-50 text-emerald-700",
    matchScore: 81,
    salary: "₹ 10 – 15 LPA",
    location: "Remote",
    type: "Full-time",
    tags: ["Pandas", "SQL", "Statistics"],
  },
  {
    id: "3",
    title: "Full Stack Developer",
    company: "InnovateTech",
    companyInitials: "IT",
    companyColor: "bg-purple-50 text-purple-700",
    matchScore: 68,
    salary: "₹ 8 – 14 LPA",
    location: "Hyderabad",
    type: "Full-time",
    tags: ["React", "Node.js", "MongoDB"],
  },
  {
    id: "4",
    title: "ML Engineer",
    company: "NeuralNest",
    companyInitials: "NN",
    companyColor: "bg-indigo-50 text-indigo-700",
    matchScore: 64,
    salary: "₹ 12 – 18 LPA",
    location: "Pune",
    type: "Full-time",
    tags: ["PyTorch", "MLOps"],
  },
  {
    id: "5",
    title: "React Developer",
    company: "PixelCraft Studio",
    companyInitials: "PC",
    companyColor: "bg-cyan-50 text-cyan-700",
    isInternship: true,
    salary: "₹ 6 – 10 LPA",
    location: "Chennai",
    type: "6 months",
    tags: ["React", "TypeScript"],
  },
];

export function CareerPlacementsPage() {
  const navigate = useNavigate();
  const [filterType, setFilterType] = useState<"All" | "Full-time" | "Internship" | "Remote">("All");
  const [searchQuery, setSearchQuery] = useState("");
  const [locationFilter, setLocationFilter] = useState("all");

  const filteredJobs = JOBS.filter((job) => {
    if (filterType === "Full-time" && job.type !== "Full-time") return false;
    if (filterType === "Internship" && !job.isInternship) return false;
    if (filterType === "Remote" && job.location !== "Remote") return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const match =
        job.title.toLowerCase().includes(q) ||
        job.company.toLowerCase().includes(q) ||
        job.tags.some((t) => t.toLowerCase().includes(q));
      if (!match) return false;
    }
    if (locationFilter !== "all" && job.location.toLowerCase() !== locationFilter.toLowerCase()) {
      return false;
    }
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Page Header matching Page 10 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#111827] tracking-tight">Career & Placements</h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500">
            Find the right opportunity for your skills
          </p>
        </div>
        <button
          type="button"
          onClick={() => navigate("/career/resumes")}
          className="inline-flex items-center gap-2 rounded-xl border border-[#E5E7EB] bg-white px-4 py-2.5 text-xs font-semibold text-[#111827] hover:bg-slate-50 hover:border-slate-300 transition-all cursor-pointer shadow-2xs self-start sm:self-auto"
        >
          <Icon name="fileText" size={15} className="text-[#635BFF]" />
          My Resume
        </button>
      </div>

      {/* Filter and Search Bar matching Page 10 */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <Icon name="search" size={15} />
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search jobs..."
            className="w-full rounded-xl border border-[#E5E7EB] bg-white py-2 pl-9 pr-3 text-xs text-slate-800 placeholder-slate-400 shadow-2xs focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/15"
          />
        </div>

        {/* Filter Pills */}
        <div className="inline-flex rounded-xl bg-slate-100 p-1 ring-1 ring-slate-200/60">
          {(["All", "Full-time", "Internship", "Remote"] as const).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setFilterType(t)}
              className={`rounded-lg px-3 py-1 text-xs font-semibold transition-all cursor-pointer ${
                filterType === t
                  ? "bg-[#635BFF] text-white shadow-2xs"
                  : "text-slate-600 hover:text-[#111827]"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Location Dropdown */}
        <div className="relative">
          <select
            value={locationFilter}
            onChange={(e) => setLocationFilter(e.target.value)}
            className="appearance-none rounded-xl border border-[#E5E7EB] bg-white px-3 py-2 pr-8 text-xs font-semibold text-slate-700 shadow-2xs hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
          >
            <option value="all">All locations</option>
            <option value="bengaluru">Bengaluru</option>
            <option value="remote">Remote</option>
            <option value="hyderabad">Hyderabad</option>
            <option value="pune">Pune</option>
            <option value="chennai">Chennai</option>
          </select>
          <Icon
            name="chevronDown"
            size={13}
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
          />
        </div>
      </div>

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2/3): Job Cards */}
        <div className="lg:col-span-2 space-y-4">
          {filteredJobs.map((job) => (
            <div
              key={job.id}
              className="rounded-xl border border-[#E5E7EB] bg-white p-5 shadow-card transition-all hover:border-slate-300"
            >
              <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
                <div className="flex items-start gap-4">
                  <div
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl font-extrabold text-sm shadow-2xs ${job.companyColor}`}
                  >
                    {job.companyInitials}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <h3 className="text-sm sm:text-base font-bold text-[#111827]">{job.title}</h3>
                      {job.matchScore && (
                        <span className="rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                          {job.matchScore}% match
                        </span>
                      )}
                      {job.isInternship && (
                        <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-600">
                          Internship
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-xs text-slate-600 font-medium">{job.company}</p>

                    <div className="mt-2.5 flex flex-wrap items-center gap-3 text-xs text-slate-500 font-medium">
                      <span>{job.salary}</span>
                      <span>•</span>
                      <span>{job.location}</span>
                      <span>•</span>
                      <span>{job.type}</span>
                    </div>

                    <div className="mt-3.5 flex flex-wrap items-center gap-1.5">
                      {job.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-lg bg-slate-50 border border-slate-100 px-2.5 py-1 text-[11px] font-medium text-slate-600"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-center">
                  <button
                    type="button"
                    className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-400 hover:text-[#111827] hover:bg-slate-50 cursor-pointer transition-colors"
                    title="Bookmark"
                  >
                    <Icon name="archive" size={15} />
                  </button>
                  <button
                    type="button"
                    onClick={() => navigate(`/jobs/board/${job.id}`)}
                    className="rounded-xl bg-[#635BFF] px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-[#5046E5] transition-all cursor-pointer"
                  >
                    Apply Now
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Right Column (1/3): Placement Profile, Applications, Upcoming Drive */}
        <div className="space-y-5">
          {/* 1. Placement Profile */}
          <div className="rounded-xl border border-[#E5E7EB] bg-white p-5 shadow-card">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-[#111827]">Placement Profile</h3>
              <span className="text-xs font-extrabold text-[#635BFF]">80%</span>
            </div>

            <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden mb-4">
              <div className="h-full bg-[#635BFF] rounded-full" style={{ width: "80%" }} />
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center gap-2 text-slate-700 font-medium">
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-[10px] font-bold">
                  ✓
                </span>
                <span>Resume uploaded</span>
              </div>
              <div className="flex items-center gap-2 text-slate-700 font-medium">
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-[10px] font-bold">
                  ✓
                </span>
                <span>2 certificates added</span>
              </div>
              <div className="flex items-center gap-2 text-slate-700 font-medium">
                <span className="flex h-4 w-4 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 text-[10px] font-bold">
                  ✓
                </span>
                <span>Skills verified by exam</span>
              </div>
              <div
                onClick={() => navigate("/career/profile")}
                className="flex items-center gap-2 text-slate-400 hover:text-[#635BFF] cursor-pointer pt-1"
              >
                <span className="h-4 w-4 rounded-full border border-slate-300" />
                <span>Add a portfolio link</span>
              </div>
            </div>
          </div>

          {/* 2. My Applications Stats */}
          <div className="rounded-xl border border-[#E5E7EB] bg-white p-5 shadow-card">
            <h3 className="text-sm font-bold text-[#111827] mb-3.5">My Applications</h3>
            <div className="grid grid-cols-3 gap-2.5 text-center">
              <div className="rounded-xl bg-blue-50/60 p-3">
                <p className="text-xl font-extrabold text-[#635BFF]">4</p>
                <p className="text-[11px] font-semibold text-slate-500 mt-0.5">Applied</p>
              </div>
              <div className="rounded-xl bg-amber-50/60 p-3">
                <p className="text-xl font-extrabold text-amber-700">2</p>
                <p className="text-[11px] font-semibold text-slate-500 mt-0.5">Shortlisted</p>
              </div>
              <div className="rounded-xl bg-emerald-50/60 p-3">
                <p className="text-xl font-extrabold text-emerald-700">1</p>
                <p className="text-[11px] font-semibold text-slate-500 mt-0.5">Interviews</p>
              </div>
            </div>
          </div>

          {/* 3. Upcoming Placement Drive Banner */}
          <div className="relative overflow-hidden rounded-xl bg-gradient-to-r from-blue-600 via-blue-700 to-indigo-700 p-5 text-white shadow-card">
            <p className="text-[10px] font-bold uppercase tracking-wider text-blue-200">
              Upcoming Placement Drive
            </p>
            <h4 className="mt-1.5 text-base font-extrabold tracking-tight">Campus Hiring Week</h4>
            <p className="mt-1 text-xs text-blue-100">24 – 28 Apr · 18 companies</p>
            <button
              type="button"
              onClick={() => navigate("/jobs/drives")}
              className="mt-4 rounded-xl bg-white px-4 py-2 text-xs font-bold text-[#635BFF] shadow-sm hover:bg-blue-50 transition-colors cursor-pointer"
            >
              Register
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
