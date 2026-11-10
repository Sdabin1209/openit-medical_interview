import { useForm } from "react-hook-form";

interface Values {
  name: string;
}

interface Props {
  onSubmit: (values: Values) => void;
}

/** 이름 입력 폼(react-hook-form). 제약은 계약의 칸 제약과 같아야 한다(예시: 1~64자). */
export function NameForm({ onSubmit }: Props) {
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Values>({ defaultValues: { name: "" } });
  return (
    <form onSubmit={(event) => void handleSubmit(onSubmit)(event)} noValidate>
      <label htmlFor="name">이름</label>
      <input
        id="name"
        aria-invalid={errors.name ? "true" : "false"}
        {...register("name", {
          required: "이름을 입력한다",
          maxLength: { value: 64, message: "64자 이하로 입력한다" },
        })}
      />
      {errors.name ? <p role="alert">{errors.name.message}</p> : null}
      <button type="submit">추가</button>
    </form>
  );
}
