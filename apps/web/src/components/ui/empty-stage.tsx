export function EmptyStage({ message }: { message: string }) {
  return (
    <div className="empty-stage">
      <span className="empty-stage-mark" aria-hidden="true">
        ○
      </span>
      <p>{message}</p>
    </div>
  );
}
