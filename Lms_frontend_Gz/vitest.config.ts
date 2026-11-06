export default {
  test: {
    globals: true,
    environment: "jsdom",
    include: ["tests/**/*.spec.ts", "tests/**/*.test.ts"],
    timeout: 30000,
  },
};
