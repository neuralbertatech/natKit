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

// --- The built-in ADL experiment as an authorable step protocol ------------
// This task list was hard-coded into the ADL/IMU experiment flow. Expressing it
// as a step protocol makes it one option among the user's own experiments: it can
// be selected, recorded and reviewed like any other, and edited afterwards
// instead of being a fixed program.
//
// The timing is a faithful translation of what the hard-coded runner did:
// a COUNTDOWN_SECONDS "get ready" before each task, the task itself for
// duration_seconds, and REST_PERIOD_SECONDS between tasks (not after the last).
import {
    newStepId,
    type ExperimentStep,
    type StepProtocol,
} from "../StreamViewer/experimentSteps";

export const ADL_PROTOCOL_ID = "adl-tasks-v1";

export function adlStepProtocol(tasks: AdlTask[] = ADL_TASKS): StepProtocol {
    const steps: ExperimentStep[] = [
        {
            id: newStepId("adl-intro"),
            kind: "instruction",
            text:
                "You will be asked to mime a series of everyday activities. " +
                "Follow each prompt; rest in between.",
            duration_s: 5,
        },
    ];

    tasks.forEach((task, index) => {
        steps.push({
            id: newStepId("adl-ready"),
            kind: "instruction",
            text: `Get ready: ${task.name}`,
            duration_s: COUNTDOWN_SECONDS,
        });
        steps.push({
            id: newStepId("adl-cue"),
            kind: "cue",
            // The task id is the class label a classifier would learn.
            label: task.id,
            text: task.instruction,
            duration_s: task.duration_seconds,
        });
        if (index < tasks.length - 1) {
            steps.push({
                id: newStepId("adl-rest"),
                kind: "rest",
                text: "Rest",
                duration_s: REST_PERIOD_SECONDS,
            });
        }
    });

    return {
        protocol_version: 1,
        protocol_id: ADL_PROTOCOL_ID,
        label: "ADL tasks",
        rest_class: "rest",
        steps,
    };
}
