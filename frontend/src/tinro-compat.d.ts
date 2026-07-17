declare module "tinro" {
  import type { SvelteComponentTyped } from "svelte";

  export interface TinroRoute {
    url: string;
    from: string;
    path: string;
    query: Record<string, string>;
    hash: string;
  }

  export interface TinroBreadcrumb {
    path: string;
    name: string;
  }

  export interface TinroRouteMeta {
    url: string;
    from?: string;
    match: string;
    pattern: string;
    breadcrumbs?: Array<TinroBreadcrumb>;
    query: Record<string, string>;
    params: Record<string, string>;
    subscribe(handler: (meta: TinroRouteMeta) => void): void;
  }

  export interface TinroRouterModeSwitcher {
    history(): () => void;
    hash(): () => void;
    memory(): () => void;
  }

  export interface TinroRouterLocationHash {
    get(): string;
    set(value: string): void;
    clear(): void;
  }

  export interface TinroRouterLocationQuery {
    get(name?: string): Record<string, string> | string;
    set(name: string, value: string | number): void;
    delete(name: string): void;
    replace(value: Record<string, string>): void;
    clear(): void;
  }

  export interface TinroRouterLocation {
    hash: TinroRouterLocationHash;
    query: TinroRouterLocationQuery;
  }

  export interface TinroRouter {
    goto(url: string, replace?: boolean): void;
    subscribe(handler: (currentRoute: TinroRoute) => void): void;
    mode: TinroRouterModeSwitcher;
    location: TinroRouterLocation;
    base(path: string): void;
    params(): Record<string, string>;
    useHashNavigation(use?: boolean): void;
    meta(): TinroRouteMeta;
  }

  export const active: any;
  export function meta(): TinroRouteMeta;
  export const router: TinroRouter;

  export class Route extends SvelteComponentTyped<
    {
      path?: string;
      fallback?: boolean;
      redirect?: string;
      firstmatch?: boolean;
      breadcrumb?: string;
    },
    Record<string, never>,
    {
      default: {
        meta: TinroRouteMeta;
        params: Record<string, string>;
      };
    }
  > {}
}
