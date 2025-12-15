<script lang="ts">
    import { Route, router, active } from "tinro";
    import Announcer from "./lib/components/announcer.svelte";
    import Transition from "./lib/components/transition.svelte";
    import Home from "./home.svelte";
    import About from "./about.svelte";
    import ImuExperiment from "./ImuExperiment/page.svelte";
    import AdlExperiment from "./AdlExperiment/page.svelte";
    import StreamViewer from "./StreamViewer/page.svelte";

    router.mode.hash();
    router.subscribe((_) => window.scrollTo(0, 0));
</script>

<nav class="navbar">
    <div class="nav-brand">
        <a href="/">natKit</a>
    </div>
    <div class="nav-links">
        <a href="/" use:active>Home</a>
        <a href="/ImuExperiment" use:active>IMU Experiment</a>
        <a href="/AdlExperiment" use:active>ADL Experiment</a>
        <a href="/StreamViewer" use:active>Stream Viewer</a>
        <a href="/about" use:active>About</a>
    </div>
</nav>

<main class="content">
    <Announcer />
    <Transition>
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
    </Transition>
</main>

<style>
    :global(body) {
        margin: 0;
        font-family:
            -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen,
            Ubuntu, sans-serif;
    }

    .navbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 1.5rem;
        height: 56px;
        background-color: #1a1a2e;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .nav-brand a {
        font-size: 1.25rem;
        font-weight: 700;
        color: #fff;
        text-decoration: none;
        letter-spacing: 0.5px;
    }

    .nav-links {
        display: flex;
        gap: 0.5rem;
    }

    .nav-links a {
        padding: 0.5rem 1rem;
        color: #a0a0b0;
        text-decoration: none;
        font-size: 0.9rem;
        font-weight: 500;
        border-radius: 6px;
        transition:
            background-color 0.2s,
            color 0.2s;
    }

    .nav-links a:hover {
        background-color: rgba(255, 255, 255, 0.1);
        color: #fff;
    }

    .nav-links a:global(.active) {
        background-color: rgba(255, 255, 255, 0.15);
        color: #fff;
    }

    .content {
        min-height: calc(100vh - 56px);
        background-color: #f5f5f7;
    }
</style>
