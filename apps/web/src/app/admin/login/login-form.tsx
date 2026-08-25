"use client";

import React, { useActionState } from "react";

import { initialLoginState, loginAction } from "./actions";

export function LoginForm({ nextPath }: { nextPath: string }) {
  const [state, action, pending] = useActionState(loginAction, initialLoginState);
  return (
    <form className="login-form" action={action}>
      <input type="hidden" name="next" value={nextPath} />
      <label><span>Administrator email</span><input type="email" name="email" autoComplete="username" required /></label>
      <label><span>Password</span><input type="password" name="password" autoComplete="current-password" /></label>
      {state.message ? <p className={`form-message form-message--${state.status}`} role="status">{state.message}</p> : null}
      <div className="button-row">
        <button className="button" type="submit" name="method" value="password" disabled={pending}>{pending ? "Checking…" : "Sign in"}</button>
        <button className="button button--secondary" type="submit" name="method" value="magic-link" disabled={pending}>Email magic link</button>
      </div>
      <p className="login-form__note">There is no signup flow. Magic-link requests set <code>shouldCreateUser=false</code>.</p>
    </form>
  );
}
