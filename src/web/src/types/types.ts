import type { ComponentType } from "react";

export interface NavTab {
  path: string;
  label: string;
  Icon: ComponentType<{ size?: number }>;
}
