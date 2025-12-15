import type { AdlTask } from "./types";
import { TEST_MODE } from "./types";

// All ADL tasks for the full experiment
const ALL_ADL_TASKS: AdlTask[] = [
  {
    id: "drink_cup",
    name: "Drinking",
    instruction: "Pick up the cup and take a drink",
    duration_seconds: 10,
    category: "upper_extremity",
  },
  {
    id: "brush_teeth",
    name: "Brushing Teeth",
    instruction: "Simulate brushing your teeth",
    duration_seconds: 15,
    category: "self_care",
  },
  {
    id: "comb_hair",
    name: "Combing Hair",
    instruction: "Comb or brush your hair",
    duration_seconds: 10,
    category: "self_care",
  },
  {
    id: "eat_fork",
    name: "Eating with Fork",
    instruction: "Simulate eating with a fork",
    duration_seconds: 10,
    category: "upper_extremity",
  },
  {
    id: "eat_spoon",
    name: "Eating with Spoon",
    instruction: "Simulate eating with a spoon",
    duration_seconds: 10,
    category: "upper_extremity",
  },
  {
    id: "reach_overhead",
    name: "Reaching Overhead",
    instruction: "Reach up as if getting something from a high shelf",
    duration_seconds: 8,
    category: "upper_extremity",
  },
  {
    id: "open_door",
    name: "Opening Door",
    instruction: "Simulate opening a door",
    duration_seconds: 8,
    category: "upper_extremity",
  },
  {
    id: "button_shirt",
    name: "Buttoning Shirt",
    instruction: "Simulate buttoning a shirt",
    duration_seconds: 15,
    category: "bilateral",
  },
  {
    id: "turn_key",
    name: "Turning Key",
    instruction: "Simulate turning a key in a lock",
    duration_seconds: 8,
    category: "upper_extremity",
  },
  {
    id: "pour_water",
    name: "Pouring Water",
    instruction: "Simulate pouring water from a pitcher",
    duration_seconds: 10,
    category: "bilateral",
  },
];

// Subset of tasks for test mode (shorter experiment)
const TEST_ADL_TASKS: AdlTask[] = [
  ALL_ADL_TASKS[0], // drink_cup
  ALL_ADL_TASKS[2], // comb_hair
  ALL_ADL_TASKS[5], // reach_overhead
];

// Export the appropriate task list based on TEST_MODE
export const ADL_TASKS: AdlTask[] = TEST_MODE ? TEST_ADL_TASKS : ALL_ADL_TASKS;

// Configuration constants
export const REST_PERIOD_SECONDS = 5;
export const COUNTDOWN_SECONDS = 3;

// Calculate total experiment duration
export function calculateTotalDuration(tasks: AdlTask[]): number {
  const taskDuration = tasks.reduce(
    (sum, task) => sum + task.duration_seconds,
    0,
  );
  const restDuration = (tasks.length - 1) * REST_PERIOD_SECONDS;
  const countdownDuration = tasks.length * COUNTDOWN_SECONDS;
  return taskDuration + restDuration + countdownDuration;
}

// Format seconds as mm:ss
export function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}
