import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "outline" | "quiet" };
export function Button({ variant = "primary", className = "", type = "button", ...props }: ButtonProps) {
  return <button className={`button button--${variant}${className ? ` ${className}` : ""}`} type={type} {...props} />;
}
