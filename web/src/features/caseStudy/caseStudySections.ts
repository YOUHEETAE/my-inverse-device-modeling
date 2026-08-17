// Section id/label pairs only — kept separate from CaseStudyPage's content
// JSX so the main Sidebar (mounted on every route) can render the section
// list as nested navigation without pulling in the page's full content/tool
// tree (CaseStudyFlow, etc.).
export const CASE_STUDY_SECTIONS: { id: string; label: string }[] = [
  { id: "overview", label: "개요" },
  { id: "channel-length", label: "Case Study 1. 채널 길이 변화" },
  { id: "oxide-thickness", label: "Case Study 2. 산화막 두께 변화" },
  { id: "body-doping", label: "Case Study 3. 바디 도핑 변화" },
  { id: "ldd-doping", label: "Case Study 4. LDD 도핑 변화" },
  { id: "sd-doping", label: "Case Study 5. S/D 도핑 변화" },
];
