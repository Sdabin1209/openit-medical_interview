import * as Dialog from "@radix-ui/react-dialog";

interface Props {
  open: boolean;
  title: string;
  description: string;
  onConfirm: () => void;
  onCancel: () => void;
}

/** 확인 대화상자. Radix UI 가 포커스 가두기, Esc 닫기, aria 속성을 맡는다(접근성). */
export function ConfirmDialog({ open, title, description, onConfirm, onCancel }: Props) {
  return (
    <Dialog.Root open={open} onOpenChange={(next) => {
        if (!next) onCancel();
      }}>
      <Dialog.Portal>
        <Dialog.Overlay />
        <Dialog.Content>
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <button type="button" onClick={onConfirm}>
            확인
          </button>
          <Dialog.Close asChild>
            <button type="button">취소</button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
