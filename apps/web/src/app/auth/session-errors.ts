export class SessionEstablishmentError extends Error {
  constructor() { super("The credentials were accepted, but the session could not be confirmed."); this.name = "SessionEstablishmentError"; }
}
