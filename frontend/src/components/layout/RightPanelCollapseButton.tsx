/** 右栏折叠按钮（放在 Tab 栏右侧）。 */

import { PanelRightClose, PanelRightOpen } from "lucide-react";
import { IconButton, Tooltip } from "@/components/_kit";
import { useUIStore } from "@/store/uiStore";

export function RightPanelCollapseButton() {
  const rightHidden = useUIStore((s) => s.rightHidden);
  const toggleRightHidden = useUIStore((s) => s.toggleRightHidden);

  return (
    <Tooltip content={rightHidden ? "展开（⌘B）" : "折叠（⌘B）"}>
      <IconButton
        label="折叠"
        tooltip={false}
        size="sm"
        icon={rightHidden ? <PanelRightOpen /> : <PanelRightClose />}
        onClick={toggleRightHidden}
      />
    </Tooltip>
  );
}
