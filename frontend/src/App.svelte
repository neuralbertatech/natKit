<script lang="ts">
  import { onMount } from "svelte";
  import { Route, router, active } from "tinro";
  import Announcer from "./lib/components/announcer.svelte";
  import Home from "./home.svelte";
  import About from "./about.svelte";
  import ImuExperiment from "./ImuExperiment/page.svelte";
  import AdlExperiment from "./AdlExperiment/page.svelte";
  import StreamViewer from "./StreamViewer/page.svelte";
  import VisualProgramming from "./VisualProgramming/page.svelte";
  import MlPipeline from "./MlPipeline/page.svelte";
  import Admin from "./Admin/page.svelte";
  import {
    authSession,
    bootstrapAdmin,
    login,
    logout,
    refreshSession,
    type AuthSession,
  } from "./auth";

  router.mode.hash();
  router.subscribe((_) => window.scrollTo(0, 0));

  let session = $state<AuthSession | null>(null);
  let loadingSession = $state(true);
  let authError = $state("");
  let authMessage = $state("");

  let loginUsername = $state("");
  let loginPassword = $state("");

  let bootstrapUsername = $state("admin");
  let bootstrapDisplayName = $state("Administrator");
  let bootstrapPassword = $state("");
  let bootstrapConfirmPassword = $state("");
  let bootstrapSecret = $state("");

  const unsubscribe = authSession.subscribe((value) => {
    session = value;
  });

  async function loadSession() {
    loadingSession = true;
    authError = "";
    try {
      await refreshSession();
    } catch (err) {
      authError = err instanceof Error ? err.message : "Failed to load session.";
    } finally {
      loadingSession = false;
    }
  }

  async function submitLogin() {
    authError = "";
    authMessage = "";
    try {
      await login(loginUsername.trim(), loginPassword);
      authMessage = "";
      loginPassword = "";
    } catch (err) {
      authError = err instanceof Error ? err.message : "Sign-in failed.";
    }
  }

  async function submitBootstrap() {
    authError = "";
    authMessage = "";
    if (bootstrapPassword !== bootstrapConfirmPassword) {
      authError = "Passwords do not match.";
      return;
    }

    try {
      await bootstrapAdmin({
        username: bootstrapUsername.trim(),
        display_name: bootstrapDisplayName.trim(),
        password: bootstrapPassword,
        bootstrap_password: bootstrapSecret.trim() || undefined,
      });
      bootstrapPassword = "";
      bootstrapConfirmPassword = "";
      bootstrapSecret = "";
    } catch (err) {
      authError = err instanceof Error ? err.message : "Bootstrap failed.";
    }
  }

  async function submitLogout() {
    authError = "";
    authMessage = "";
    try {
      await logout();
      loginPassword = "";
    } catch (err) {
      authError = err instanceof Error ? err.message : "Sign-out failed.";
    }
  }

  onMount(() => {
    loadSession();
    return () => unsubscribe();
  });
</script>

{#if loadingSession}
  <main class="auth-shell">
    <section class="auth-card">
      <h1>natKit</h1>
      <p>Loading session...</p>
    </section>
  </main>
{:else if !session?.authenticated}
  <main class="auth-shell">
    <section class="auth-card">
      <div class="auth-header">
        <h1>natKit</h1>
        <p>
          {#if session?.bootstrap_required}
            Create the first administrator before using the control surfaces.
          {:else}
            Sign in to access the site.
          {/if}
        </p>
      </div>

      {#if authError}
        <div class="banner error">{authError}</div>
      {/if}
      {#if authMessage}
        <div class="banner ok">{authMessage}</div>
      {/if}

      {#if session?.bootstrap_required}
        <div class="auth-grid">
          <label>
            <span>Username</span>
            <input bind:value={bootstrapUsername} placeholder="admin" />
          </label>
          <label>
            <span>Display name</span>
            <input bind:value={bootstrapDisplayName} placeholder="Administrator" />
          </label>
          <label>
            <span>Password</span>
            <input bind:value={bootstrapPassword} type="password" placeholder="At least 10 characters" />
          </label>
          <label>
            <span>Confirm password</span>
            <input bind:value={bootstrapConfirmPassword} type="password" placeholder="Repeat password" />
          </label>
          {#if session.bootstrap_mode === "password"}
            <label class="full">
              <span>Bootstrap password from backend logs</span>
              <input bind:value={bootstrapSecret} type="password" placeholder="Paste the logged bootstrap password" />
            </label>
          {/if}
        </div>
        <button class="primary full-button" onclick={submitBootstrap}>Create initial admin</button>
      {:else}
        <div class="auth-grid">
          <label>
            <span>Username</span>
            <input bind:value={loginUsername} placeholder="Username" />
          </label>
          <label>
            <span>Password</span>
            <input bind:value={loginPassword} type="password" placeholder="Password" />
          </label>
        </div>
        <button class="primary full-button" onclick={submitLogin}>Sign in</button>
      {/if}
    </section>
  </main>
{:else}
  <nav class="navbar">
    <div class="nav-brand">
      <a href="/">natKit</a>
    </div>
    <div class="nav-links">
      <a href="/" use:active>Home</a>
      <a href="/ImuExperiment" use:active>IMU Experiment</a>
      <a href="/AdlExperiment" use:active>ADL Experiment</a>
      <a href="/StreamViewer" use:active>Stream Viewer</a>
      <a href="/VisualProgramming" use:active>Visual Programming</a>
      <a href="/MlPipeline" use:active>ML Pipeline</a>
      {#if session.user?.is_admin}
        <a href="/Admin" use:active>Admin</a>
      {/if}
      <a href="/about" use:active>About</a>
    </div>
    <div class="nav-user">
      <span>{session.user?.display_name || session.user?.username}</span>
      <button onclick={submitLogout}>Sign out</button>
    </div>
  </nav>

  <main class="content">
    <Announcer />
    <Route path="/">
      <Home />
    </Route>
    <Route path="/about">
      <About />
    </Route>
    <Route path="/ImuExperiment">
      <ImuExperiment />
    </Route>
    <Route path="/AdlExperiment">
      <AdlExperiment />
    </Route>
    <Route path="/StreamViewer">
      <StreamViewer />
    </Route>
    <Route path="/VisualProgramming">
      <VisualProgramming />
    </Route>
    <Route path="/MlPipeline">
      <MlPipeline />
    </Route>
    <Route path="/Admin">
      <Admin />
    </Route>
  </main>
{/if}

<style>
  :global(body) {
    margin: 0;
    font-family:
      -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
      Ubuntu, sans-serif;
    background: #f5f5f7;
    color: #111827;
  }

  .navbar {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 1rem;
    padding: 0 1.5rem;
    min-height: 56px;
    background-color: #111827;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .nav-brand a {
    font-size: 1.1rem;
    font-weight: 700;
    color: #fff;
    text-decoration: none;
  }

  .nav-links {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .nav-links a,
  .nav-user button {
    padding: 0.45rem 0.8rem;
    color: #d1d5db;
    text-decoration: none;
    font-size: 0.9rem;
    border-radius: 6px;
    transition:
      background-color 0.2s,
      color 0.2s;
  }

  .nav-links a:hover,
  .nav-user button:hover {
    background-color: rgba(255, 255, 255, 0.08);
    color: #fff;
  }

  .nav-links a:global(.active) {
    background-color: rgba(255, 255, 255, 0.14);
    color: #fff;
  }

  .nav-user {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    color: #e5e7eb;
    font-size: 0.9rem;
  }

  .nav-user button {
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: transparent;
    cursor: pointer;
    font: inherit;
  }

  .content {
    min-height: calc(100vh - 56px);
  }

  .auth-shell {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 1.5rem;
  }

  .auth-card {
    width: min(560px, 100%);
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 1.5rem;
    box-shadow: 0 12px 30px rgba(15, 23, 42, 0.08);
  }

  .auth-header h1 {
    margin: 0;
    font-size: 1.8rem;
  }

  .auth-header p {
    margin: 0.35rem 0 0;
    color: #4b5563;
  }

  .auth-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.85rem;
    margin-top: 1rem;
  }

  .full {
    grid-column: 1 / -1;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.9rem;
  }

  input {
    min-height: 42px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    padding: 0.65rem 0.75rem;
    font: inherit;
  }

  button {
    min-height: 42px;
    border-radius: 6px;
    border: 1px solid transparent;
    font: inherit;
  }

  .primary {
    background: #1f4a8a;
    color: #fff;
    cursor: pointer;
  }

  .full-button {
    width: 100%;
    margin-top: 1rem;
  }

  .banner {
    margin-top: 1rem;
    padding: 0.8rem 0.9rem;
    border-radius: 6px;
    font-size: 0.95rem;
  }

  .banner.ok {
    background: #e6f4ea;
    color: #1f5133;
  }

  .banner.error {
    background: #fce8e8;
    color: #8b1e1e;
  }

  @media (max-width: 980px) {
    .navbar {
      grid-template-columns: 1fr;
      padding: 0.75rem 1rem;
    }

    .nav-user {
      justify-content: space-between;
    }
  }
</style>
