import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { markOnboardingCompleteThisTab } from "../../app/auth/onboarding-state";
import { useAuth } from "../../app/auth/auth-context";
import { Button } from "../../shared/components/Button";

const steps = [
  { title: "Welcome to LexAware Student", text: "A calm starting point for understanding questions that come up in student life. You choose what to explore and what to do next." },
  { title: "Information for real questions", text: "LexAware is designed to explain legal-awareness topics, help make sense of documents, and point toward practical next steps and support." },
  { title: "Your privacy matters", text: "This introduction does not ask for personal or case details. Don’t share sensitive information unless a specific feature asks for it and you are comfortable proceeding." },
  { title: "Understand the limits", text: "Some supported experiences may use AI to help explain source-based information. AI can be incomplete or mistaken; check cited sources and seek qualified professional help when needed. LexAware is not legal representation." },
];

export function OnboardingPage() {
  const { session } = useAuth();
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const user = session.status === "authenticated" ? session.user : null;
  useEffect(() => { titleRef.current?.focus(); }, [step]);

  function finish() {
    if (user) markOnboardingCompleteThisTab(user.id);
    navigate("/app", { replace: true });
  }

  const current = steps[step]!;
  return <section aria-labelledby="onboarding-title" className="onboarding page-container">
    <p className="eyebrow">Getting started · Step {step + 1} of {steps.length}</p>
    <progress aria-label={`Getting started step ${step + 1} of ${steps.length}`} className="onboarding__progress" max={steps.length} value={step + 1} />
    <div aria-live="polite" className="onboarding__card"><h1 id="onboarding-title" ref={titleRef} tabIndex={-1}>{current.title}</h1><p>{current.text}</p></div>
    <p className="onboarding__persistence">This welcome flow is not saved to your account yet. Finishing or skipping it is remembered only in this browser tab.</p>
    <div className="onboarding__actions">{step > 0 && <Button onClick={() => setStep((value) => value - 1)} variant="outline">Back</Button>}{step < steps.length - 1 ? <Button onClick={() => setStep((value) => value + 1)}>Continue</Button> : <Button onClick={finish}>Continue to your account</Button>}<button className="text-link onboarding__skip" onClick={finish} type="button">Skip introduction</button></div>
  </section>;
}
