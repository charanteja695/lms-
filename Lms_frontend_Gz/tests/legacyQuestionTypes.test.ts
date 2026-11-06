import { describe, expect, it } from "vitest";
import { fromPaperQuestionType, toPaperQuestionType } from "../legacyQuestionTypes";

describe("legacyQuestionTypes", () => {
  describe("toPaperQuestionType", () => {
    it("keeps single_choice as single_choice", () => {
      expect(toPaperQuestionType("single_choice")).toBe("single_choice");
    });

    it("maps multiple_choice and unknown values onto multiple_choice", () => {
      expect(toPaperQuestionType("multiple_choice")).toBe("multiple_choice");
      expect(toPaperQuestionType("")).toBe("multiple_choice");
      expect(toPaperQuestionType("true_false")).toBe("multiple_choice");
      expect(toPaperQuestionType(null)).toBe("multiple_choice");
      expect(toPaperQuestionType(undefined)).toBe("multiple_choice");
    });
  });

  describe("fromPaperQuestionType", () => {
    it("maps the catalog types back to the legacy set", () => {
      expect(fromPaperQuestionType("mcq_single")).toBe("single_choice");
      expect(fromPaperQuestionType("mcq_multi")).toBe("multiple_choice");
      expect(fromPaperQuestionType("true_false")).toBe("multiple_choice");
      expect(fromPaperQuestionType("fill_in")).toBe("multiple_choice");
      expect(fromPaperQuestionType("match")).toBe("multiple_choice");
      expect(fromPaperQuestionType("ordering")).toBe("multiple_choice");
      expect(fromPaperQuestionType("coding")).toBe("multiple_choice");
      expect(fromPaperQuestionType("sql")).toBe("multiple_choice");
      expect(fromPaperQuestionType("subjective")).toBe("multiple_choice");
      expect(fromPaperQuestionType("file_submission")).toBe("multiple_choice");
    });
  });
});
