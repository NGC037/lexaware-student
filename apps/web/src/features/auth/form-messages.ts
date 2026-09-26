import { ApiError } from "../../api/client";
import { SessionEstablishmentError } from "../../app/auth/session-errors";

export function safeRegistrationError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 400) return "Choose a password that is at least 12 characters and is not commonly used.";
    if (error.status === 422) return "Check the email address and password requirements, then try again.";
    if (error.status === 429) return "There have been several attempts. Wait a little while before trying again.";
    if (error.status >= 500) return "We couldn’t create the account right now. Please try again shortly.";
    if (error.status >= 400) return "Check the information and try again.";
  }
  return "We couldn’t reach LexAware. Check your connection and try again.";
}

export function safeLoginError(error: unknown): string {
  if (error instanceof SessionEstablishmentError) return "Your credentials were accepted, but we couldn’t confirm the session. Check your connection and try again.";
  if (error instanceof ApiError) {
    if (error.status === 401) return "The email or password is incorrect. Check your details and try again.";
    if (error.status === 422) return "Enter a valid email address and a password, then try again.";
    if (error.status === 429) return "There have been several attempts. Wait a little while before trying again.";
    if (error.status >= 500) return "We couldn’t sign you in right now. Please try again shortly.";
    if (error.status >= 400) return "We couldn’t sign you in. Check your details and try again.";
  }
  return "We couldn’t reach LexAware. Check your connection and try again.";
}
