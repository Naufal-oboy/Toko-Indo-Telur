-- Payment workflow: receipts baru dimulai tanpa metode pembayaran.
-- Runner menjalankan file ini dalam satu transaksi dan mencatat checksum-nya.

ALTER TABLE transactions
  ALTER COLUMN payment_method DROP NOT NULL,
  ALTER COLUMN payment_method DROP DEFAULT,
  ALTER COLUMN payment_status SET DEFAULT 'unpaid',
  ADD COLUMN paid_at TIMESTAMPTZ;

-- Pada skema sebelum migration ini, dashboard selalu membuat receipt unpaid
-- sementara default payment_method masih 'cash'. Status unpaid adalah sumber
-- data yang pasti bahwa metode tersebut belum dipilih, sehingga aman dinormalisasi.
UPDATE transactions
SET payment_method = NULL
WHERE payment_status = 'unpaid';

ALTER TABLE transactions
  DROP CONSTRAINT ck_transactions_payment_method,
  DROP CONSTRAINT ck_transactions_payment_status,
  ADD CONSTRAINT ck_transactions_payment_method
    CHECK (payment_method IS NULL OR payment_method IN ('cash', 'transfer')),
  ADD CONSTRAINT ck_transactions_payment_status
    CHECK (payment_status IN ('unpaid', 'paid', 'partial')),
  ADD CONSTRAINT ck_transactions_payment_state
    CHECK (
      (payment_status = 'unpaid' AND payment_method IS NULL AND paid_at IS NULL)
      OR
      (payment_status IN ('paid', 'partial') AND payment_method IN ('cash', 'transfer'))
    );
