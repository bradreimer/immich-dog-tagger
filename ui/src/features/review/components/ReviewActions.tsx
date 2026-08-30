import { IdentityChooser } from "./IdentityChooser";

interface Props {
  identities: string[];
  species?: string;
  predictedIdentity?: string | null;
  onCorrect: (identity: string) => void;
  onSkip?: () => void;
  disabled?: boolean;
}

export function ReviewActions(props: Props) {
  return <IdentityChooser {...props} />;
}