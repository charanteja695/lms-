import type { Id } from "@/core/api/types";

export interface Person {
  user_id: Id;
  full_name: string;
}

export interface ClassSection {
  section_id: Id;
  program_id: Id;
  year_of_study: number;
  name: string;
  label: string;
  class_teacher: Person | null;
  student_count: number;
}

export interface Program {
  program_id: Id;
  department_id: Id;
  name: string;
  code: string;
  duration_years: number;
  sections: ClassSection[];
}

export interface Department {
  department_id: Id;
  name: string;
  code: string;
  head: Person | null;
  programs: Program[];
}

export interface AcademicRights {
  create: boolean;
  update: boolean;
  delete: boolean;
}

export interface AcademicStructure {
  organization_id: Id;
  can_manage: boolean;
  /** The matrix cells held here: create, update (also placing students), delete. */
  rights: AcademicRights;
  departments: Department[];
  totals: { departments: number; programs: number; sections: number; placed_students: number };
}

export interface SectionStudent {
  user_id: Id;
  full_name: string;
  admission_number: string | null;
  email: string | null;
}

export interface DepartmentBody {
  name?: string;
  code?: string;
  head_user_id?: string | null;
}

export interface ProgramBody {
  department_id?: string;
  name?: string;
  code?: string;
  duration_years?: number;
}

export interface SectionBody {
  program_id?: string;
  year_of_study?: number;
  name?: string;
  class_teacher_id?: string | null;
}
