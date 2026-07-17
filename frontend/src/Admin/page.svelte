<script lang="ts">
  import { onMount } from "svelte";
  import { authSession, createUser, deleteUser, listUsers, type ManagedUser, updateUser } from "../auth";

  let session = $state<{ user: { username: string; is_admin: boolean } | null } | null>(null);
  let users = $state<ManagedUser[]>([]);
  let loading = $state(true);
  let error = $state("");
  let message = $state("");

  let newUsername = $state("");
  let newDisplayName = $state("");
  let newPassword = $state("");
  let newIsAdmin = $state(false);
  let newEnabled = $state(true);
  let newSharedComputeAccess = $state(true);

  let passwordDrafts = $state<Record<string, string>>({});

  const unsubscribe = authSession.subscribe((value) => {
    session = value ? { user: value.user ? { username: value.user.username, is_admin: value.user.is_admin } : null } : null;
  });

  async function loadUsers() {
    loading = true;
    error = "";
    try {
      users = await listUsers();
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to load users.";
    } finally {
      loading = false;
    }
  }

  async function submitCreateUser() {
    error = "";
    message = "";
    try {
      await createUser({
        username: newUsername.trim(),
        display_name: newDisplayName.trim(),
        password: newPassword,
        is_admin: newIsAdmin,
        enabled: newEnabled,
        shared_compute_access: newSharedComputeAccess,
      });
      message = "User created.";
      newUsername = "";
      newDisplayName = "";
      newPassword = "";
      newIsAdmin = false;
      newEnabled = true;
      newSharedComputeAccess = true;
      await loadUsers();
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to create user.";
    }
  }

  async function saveUser(user: ManagedUser) {
    error = "";
    message = "";
    try {
      const password = passwordDrafts[user.username]?.trim() ?? "";
      await updateUser({
        username: user.username,
        display_name: user.display_name,
        is_admin: user.is_admin,
        enabled: user.enabled,
        shared_compute_access: user.shared_compute_access,
        ...(password ? { password } : {}),
      });
      passwordDrafts = { ...passwordDrafts, [user.username]: "" };
      message = `Saved ${user.username}.`;
      await loadUsers();
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to update user.";
    }
  }

  async function removeUser(username: string) {
    error = "";
    message = "";
    try {
      await deleteUser(username);
      message = `Deleted ${username}.`;
      await loadUsers();
    } catch (err) {
      error = err instanceof Error ? err.message : "Failed to delete user.";
    }
  }

  onMount(() => {
    loadUsers();
    return () => unsubscribe();
  });
</script>

{#if !session?.user?.is_admin}
  <section class="panel">
    <h1>Admin</h1>
    <p>Admin access is required.</p>
  </section>
{:else}
  <section class="panel">
    <div class="panel-header">
      <div>
        <h1>Users</h1>
        <p>Manage local accounts for the Drogon backend and Stream Viewer.</p>
      </div>
    </div>

    {#if error}
      <div class="banner error">{error}</div>
    {/if}
    {#if message}
      <div class="banner ok">{message}</div>
    {/if}

    <div class="create-grid">
      <label>
        <span>Username</span>
        <input bind:value={newUsername} placeholder="operator" />
      </label>
      <label>
        <span>Display name</span>
        <input bind:value={newDisplayName} placeholder="Operator" />
      </label>
      <label>
        <span>Password</span>
        <input bind:value={newPassword} type="password" placeholder="At least 10 characters" />
      </label>
      <label class="toggle">
        <input bind:checked={newIsAdmin} type="checkbox" />
        <span>Admin</span>
      </label>
      <label class="toggle">
        <input bind:checked={newEnabled} type="checkbox" />
        <span>Enabled</span>
      </label>
      <label class="toggle">
        <input bind:checked={newSharedComputeAccess} type="checkbox" />
        <span>Shared pool access</span>
      </label>
      <button class="primary" onclick={submitCreateUser}>Create user</button>
    </div>
  </section>

  <section class="panel">
    <div class="table-header">
      <h2>Current users</h2>
      <button onclick={loadUsers}>Refresh</button>
    </div>

    {#if loading}
      <p>Loading users...</p>
    {:else}
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Status</th>
              <th>Compute</th>
              <th>Last login</th>
              <th>Password reset</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {#each users as user (user.username)}
              <tr>
                <td>
                  <input bind:value={user.display_name} />
                  <div class="muted">@{user.username}</div>
                </td>
                <td>
                  <label class="toggle">
                    <input bind:checked={user.is_admin} type="checkbox" />
                    <span>Admin</span>
                  </label>
                </td>
                <td>
                  <label class="toggle">
                    <input bind:checked={user.enabled} type="checkbox" />
                    <span>Enabled</span>
                  </label>
                </td>
                <td>
                  <label class="toggle">
                    <input bind:checked={user.shared_compute_access} type="checkbox" />
                    <span>Shared</span>
                  </label>
                </td>
                <td>{user.last_login_at_us ? new Date(user.last_login_at_us / 1000).toLocaleString() : "Never"}</td>
                <td>
                  <input
                    bind:value={passwordDrafts[user.username]}
                    type="password"
                    placeholder="Leave empty"
                  />
                </td>
                <td class="actions">
                  <button class="primary" onclick={() => saveUser(user)}>Save</button>
                  <button
                    class="danger"
                    disabled={user.username === session?.user?.username}
                    onclick={() => removeUser(user.username)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
{/if}

<style>
  .panel {
    max-width: 1180px;
    margin: 0 auto;
    padding: 1.5rem;
  }

  .panel-header,
  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1rem;
  }

  .create-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 0.75rem;
    margin-top: 1rem;
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.9rem;
    color: #2d3748;
  }

  .toggle {
    flex-direction: row;
    align-items: center;
    gap: 0.5rem;
    padding-top: 1.7rem;
  }

  input {
    min-height: 40px;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
    padding: 0.6rem 0.75rem;
    font: inherit;
    background: #fff;
  }

  button {
    min-height: 40px;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
    padding: 0.65rem 0.9rem;
    background: #fff;
    cursor: pointer;
    font: inherit;
  }

  button.primary {
    background: #1f4a8a;
    border-color: #1f4a8a;
    color: #fff;
  }

  button.danger {
    color: #8b1e1e;
    border-color: #e2b8b8;
  }

  button:disabled {
    opacity: 0.55;
    cursor: not-allowed;
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

  .table-wrap {
    margin-top: 1rem;
    overflow-x: auto;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    background: #fff;
  }

  th,
  td {
    padding: 0.8rem 0.65rem;
    border-bottom: 1px solid #e5e7eb;
    vertical-align: top;
    text-align: left;
  }

  th {
    font-size: 0.78rem;
    text-transform: uppercase;
    color: #4a5568;
  }

  .actions {
    display: flex;
    gap: 0.5rem;
  }

  .muted {
    margin-top: 0.25rem;
    color: #6b7280;
    font-size: 0.82rem;
  }

  h1,
  h2,
  p {
    margin: 0;
  }

  p {
    margin-top: 0.3rem;
    color: #4b5563;
  }
</style>
