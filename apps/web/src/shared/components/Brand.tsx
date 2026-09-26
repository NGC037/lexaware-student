import { Link } from "react-router";

export function Brand({ onNavigate, to = "/" }: { onNavigate?: () => void; to?: string }) {
  return <Link aria-label="LexAware Student home" className="brand" to={to} onClick={onNavigate}>
    <svg aria-hidden="true" className="brand__mark" viewBox="0 0 44 44" fill="none">
      <path d="M22 3.5 38 9v12.2c0 9.2-6.4 15.8-16 19.3C12.4 37 6 30.4 6 21.2V9l16-5.5Z" stroke="currentColor" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M12.5 15.5c3.4-.7 6.4.1 9.5 2.3v13.1c-3-2.1-6.2-2.8-9.5-2.1V15.5Zm19 0c-3.4-.7-6.4.1-9.5 2.3v13.1c3-2.1 6.2-2.8 9.5-2.1V15.5Z" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      <path d="M27 25h5l-2.2-2.2M32 25l-2.2 2.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg><span className="brand__name">LexAware <span>Student</span></span>
  </Link>;
}
