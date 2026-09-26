import { BrowserRouter, Navigate, Route, Routes } from "react-router";
import { AuthProvider } from "./auth/AuthProvider";
import { ProtectedRoute, PublicAuthRoute } from "./auth/RouteAccess";
import { AppHomePage } from "../features/application/AppHomePage";
import { RightsExplorerPage } from "../features/knowledge/RightsExplorerPage";
import { StudentArticlePage } from "../features/knowledge/StudentArticlePage";
import { ComplaintGuidesPage, ComplaintGuidePage } from "../features/knowledge/ComplaintGuidancePage";
import { HelpDirectoryPage } from "../features/knowledge/HelpDirectoryPage";
import { LoginPage } from "../features/auth/LoginPage";
import { RegisterPage } from "../features/auth/RegisterPage";
import { LandingPage } from "../features/landing/LandingPage";
import { NotFoundPage } from "../features/landing/NotFoundPage";
import { OnboardingPage } from "../features/onboarding/OnboardingPage";
import { AuthenticatedLayout } from "../shared/layout/AuthenticatedLayout";
import { PublicAuthLayout } from "../shared/layout/PublicAuthLayout";
import { SiteLayout } from "../shared/layout/SiteLayout";

export function App() {
  return <BrowserRouter><AuthProvider><Routes>
    <Route element={<SiteLayout />}><Route index element={<LandingPage />} /><Route path="/home" element={<Navigate to="/" replace />} /><Route path="*" element={<NotFoundPage />} /></Route>
    <Route element={<PublicAuthLayout />}><Route element={<PublicAuthRoute />}><Route path="/register" element={<RegisterPage />} /><Route path="/login" element={<LoginPage />} /></Route></Route>
    <Route element={<ProtectedRoute allowBeforeOnboarding />}><Route element={<AuthenticatedLayout />}>
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/app" element={<AppHomePage />} />
        <Route path="/app/rights" element={<RightsExplorerPage />} />
        <Route path="/app/rights/:slug" element={<StudentArticlePage />} />
        <Route path="/app/complaints" element={<ComplaintGuidesPage />} />
        <Route path="/app/complaints/:slug" element={<ComplaintGuidePage />} />
        <Route path="/app/help" element={<HelpDirectoryPage />} />
      </Route>
    </Route></Route>
  </Routes></AuthProvider></BrowserRouter>;
}
