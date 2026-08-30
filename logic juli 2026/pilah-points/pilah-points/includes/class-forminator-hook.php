<?php
if ( ! defined( 'ABSPATH' ) ) exit;

// ============================================================
// KONFIGURASI: Isi dengan ID form Forminator Anda
// ============================================================
define( 'PILAH_FORM_TOPUP_ID',    0 ); // ← GANTI dengan ID form topup
define( 'PILAH_FORM_WITHDRAW_ID', 0 ); // ← GANTI dengan ID form withdraw

define( 'PILAH_FIELD_TID',          'text-1' );     // ← sesuaikan dengan Element ID field TID di Forminator
define( 'PILAH_FIELD_POINT_AMOUNT', 'number-1' );   // ← sesuaikan dengan Element ID field Amount di Forminator
define( 'PILAH_FIELD_NOTES',        'textarea-1' ); // ← sesuaikan dengan Element ID field Notes (opsional)

class Pilah_Forminator_Hook {

    public static function init() {
        add_action( 'forminator_form_after_save_entry',
            [ __CLASS__, 'on_form_submit' ], 10, 2 );
    }

    public static function on_form_submit( $form_id, $response ) {
        error_log( '[Pilah DEBUG] Hook fired. form_id=' . $form_id );

        if ( $form_id == PILAH_FORM_TOPUP_ID ) {
            self::handle_topup( $form_id, $response );
        } elseif ( $form_id == PILAH_FORM_WITHDRAW_ID ) {
            self::handle_withdraw( $form_id, $response );
        } else {
            error_log( '[Pilah DEBUG] form_id tidak cocok dengan TOPUP(' . PILAH_FORM_TOPUP_ID . ') atau WITHDRAW(' . PILAH_FORM_WITHDRAW_ID . ')' );
        }
    }

    private static function handle_topup( $form_id, $response ) {
        error_log( '[Pilah DEBUG] handle_topup mulai. is_user_logged_in=' . ( is_user_logged_in() ? 'yes' : 'no' ) );

        if ( ! is_user_logged_in() ) { error_log( '[Pilah DEBUG] STOP: user tidak login' ); return; }

        $user_id  = get_current_user_id();

        // Ambil entry_id dari database Forminator (bukan dari $response)
        $entry_id = self::get_latest_entry_id( $form_id );
        error_log( '[Pilah DEBUG] user_id=' . $user_id . ' entry_id=' . $entry_id );

        // Idempotency check
        if ( $entry_id ) {
            global $wpdb;
            $existing = $wpdb->get_var( $wpdb->prepare(
                "SELECT id FROM pilah_transaction WHERE forminator_entry_id = %d LIMIT 1",
                $entry_id ) );
            if ( $existing ) { error_log( '[Pilah] Duplicate entry_id ' . $entry_id ); return; }
        }

        // Baca field dari database Forminator langsung
        $fields = self::parse_form_fields( $entry_id );
        error_log( '[Pilah DEBUG] parsed fields=' . print_r( $fields, true ) );

        $tid    = sanitize_text_field( $fields[ PILAH_FIELD_TID ] ?? '' );
        $amount = floatval( $fields[ PILAH_FIELD_POINT_AMOUNT ] ?? 0 );
        $notes  = sanitize_textarea_field( $fields[ PILAH_FIELD_NOTES ] ?? '' );
        error_log( '[Pilah DEBUG] tid=' . $tid . ' amount=' . $amount );

        if ( empty( $tid ) ) { error_log( '[Pilah] TID kosong' ); return; }
        if ( ! self::is_tid_unique( $tid ) ) {
            Pilah_Security::write_audit_log( $user_id, 'duplicate_tid_attempt', 'transaction',
                0, null, [ 'tid' => $tid, 'entry_id' => $entry_id ] );
            error_log( '[Pilah DEBUG] STOP: TID sudah pernah dipakai' );
            return;
        }
        if ( $amount <= 0 || $amount > 9999 ) { error_log( '[Pilah] Amount invalid: ' . $amount ); return; }

        error_log( '[Pilah DEBUG] Memanggil credit_point untuk user_id=' . $user_id . ' amount=' . $amount );
        $result = Pilah_Point_Handler::credit_point( $user_id, $amount, $tid, 'topup', [
            'idempotency_key'     => 'form_' . $entry_id,
            'forminator_entry_id' => $entry_id,
            'notes'               => $notes,
        ]);
        error_log( '[Pilah DEBUG] Hasil credit_point=' . print_r( $result, true ) );
    }

    private static function handle_withdraw( $form_id, $response ) {
        if ( ! is_user_logged_in() ) return;

        $user_id  = get_current_user_id();
        $entry_id = self::get_latest_entry_id( $form_id );

        if ( $entry_id ) {
            global $wpdb;
            $existing = $wpdb->get_var( $wpdb->prepare(
                "SELECT id FROM pilah_transaction WHERE forminator_entry_id = %d AND category = 'withdraw' LIMIT 1",
                $entry_id ) );
            if ( $existing ) return;
        }

        $result = Pilah_Point_Handler::debit_point_for_withdraw( $user_id );
        if ( $result['success'] ) {
            set_transient( 'pilah_last_voucher_' . $user_id, $result['voucher_code'], 300 );
        }
        error_log( '[Pilah DEBUG] Hasil withdraw=' . print_r( $result, true ) );
    }

    private static function is_tid_unique( $tid ) {
        global $wpdb;
        $exists = $wpdb->get_var( $wpdb->prepare(
            "SELECT COUNT(*) FROM pilah_transaction WHERE tid = %s", $tid ) );
        return intval( $exists ) === 0;
    }

    /**
     * Ambil entry_id terbaru dari tabel Forminator untuk form tertentu.
     * Karena $response tidak membawa entry_id di Forminator Free,
     * kita query langsung entry paling baru milik form ini.
     */
    private static function get_latest_entry_id( $form_id ) {
        global $wpdb;
        $table = $wpdb->prefix . 'frmt_form_entry';
        $entry_id = $wpdb->get_var( $wpdb->prepare(
            "SELECT entry_id FROM {$table} WHERE form_id = %d ORDER BY entry_id DESC LIMIT 1",
            intval( $form_id )
        ) );
        return intval( $entry_id );
    }

    /**
     * Baca field data dari tabel meta Forminator berdasarkan entry_id.
     * Mengembalikan array [ 'field_name' => 'field_value', ... ]
     */
    private static function parse_form_fields( $entry_id ) {
        global $wpdb;
        if ( ! $entry_id ) return [];

        $table = $wpdb->prefix . 'frmt_form_entry_meta';
        $rows  = $wpdb->get_results( $wpdb->prepare(
            "SELECT meta_key, meta_value FROM {$table} WHERE entry_id = %d",
            intval( $entry_id )
        ) );

        $fields = [];
        foreach ( $rows as $row ) {
            // meta_value bisa tersimpan sebagai JSON array, unserialize, atau plain string
            $value = $row->meta_value;
            $decoded = json_decode( $value, true );
            if ( json_last_error() === JSON_ERROR_NONE && is_array( $decoded ) ) {
                // Forminator kadang simpan sebagai {"value":"isi_field"}
                $fields[ $row->meta_key ] = $decoded['value'] ?? reset( $decoded );
            } else {
                $fields[ $row->meta_key ] = $value;
            }
        }

        error_log( '[Pilah DEBUG] raw meta rows=' . print_r( $rows, true ) );
        return $fields;
    }
}
