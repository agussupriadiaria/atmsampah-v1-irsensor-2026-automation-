<?php
if ( ! defined( 'ABSPATH' ) ) exit;

class Pilah_Point_Handler {

    public static function init() {
        add_action( 'um_registration_complete', [ __CLASS__, 'on_user_register' ], 10, 2 );
    }

    public static function on_user_register( $user_id, $args ) {
        global $wpdb;
        $user_id = intval( $user_id );
        if ( ! $user_id ) return;

        $existing = Pilah_Database::get_user_point( $user_id );
        if ( $existing ) return;

        $wpdb->query( 'START TRANSACTION' );
        try {
            $inserted = $wpdb->insert( 'pilah_point',
                [ 'user_id' => $user_id, 'balance' => 0.00, 'version' => 0 ],
                [ '%d', '%f', '%d' ]
            );
            if ( false === $inserted ) throw new Exception( 'Gagal insert pilah_point' );

            $wpdb->insert( 'pilah_transaction', [
                'user_id'        => $user_id,
                'type'           => 'credit',
                'category'       => 'registration',
                'amount'         => 0.00,
                'balance_before' => 0.00,
                'balance_after'  => 0.00,
                'status'         => 'completed',
                'notes'          => 'Inisialisasi akun baru',
                'ip_address'     => Pilah_Security::get_client_ip(),
            ], [ '%d', '%s', '%s', '%f', '%f', '%f', '%s', '%s', '%s' ] );

            $wpdb->query( 'COMMIT' );
            Pilah_Usermeta_Sync::set_display_point( $user_id, 0 );
            Pilah_Security::write_audit_log( $user_id, 'user_registered', 'point',
                $wpdb->insert_id, null, [ 'balance' => 0 ] );

        } catch ( Exception $e ) {
            $wpdb->query( 'ROLLBACK' );
            error_log( '[Pilah] Registrasi gagal: ' . $e->getMessage() );
        }
    }

    public static function credit_point( $user_id, $amount, $tid, $category = 'topup', $meta = [] ) {
        global $wpdb;
        $user_id = intval( $user_id );
        $amount  = floatval( $amount );
        $tid     = sanitize_text_field( $tid );

        if ( $amount <= 0 ) return [ 'success' => false, 'message' => 'Jumlah point tidak valid' ];
        if ( ! Pilah_Security::check_rate_limit( $user_id, 'topup', PILAH_RATE_LIMIT_TOPUP ) )
            return [ 'success' => false, 'message' => 'Terlalu banyak transaksi. Coba lagi nanti.' ];

        $wpdb->query( 'START TRANSACTION' );
        try {
            $locked_row = $wpdb->get_row( $wpdb->prepare(
                "SELECT * FROM pilah_point WHERE user_id = %d FOR UPDATE", $user_id ) );
            if ( ! $locked_row ) throw new Exception( 'Record point user tidak ditemukan' );

            $balance_before = floatval( $locked_row->balance );
            $balance_after  = $balance_before + $amount;
            $new_version    = intval( $locked_row->version ) + 1;

            $updated = $wpdb->query( $wpdb->prepare(
                "UPDATE pilah_point SET balance = %f, version = %d WHERE user_id = %d AND version = %d",
                $balance_after, $new_version, $user_id, intval( $locked_row->version ) ) );
            if ( ! $updated ) throw new Exception( 'Optimistic lock failed' );

            $wpdb->insert( 'pilah_transaction', [
                'user_id'             => $user_id,
                'type'                => 'credit',
                'category'            => $category,
                'amount'              => $amount,
                'balance_before'      => $balance_before,
                'balance_after'       => $balance_after,
                'status'              => 'completed',
                'tid'                 => $tid ?: null,
                'idempotency_key'     => $meta['idempotency_key'] ?? null,
                'forminator_entry_id' => $meta['forminator_entry_id'] ?? null,
                'notes'               => $meta['notes'] ?? null,
                'ip_address'          => Pilah_Security::get_client_ip(),
                'user_agent'          => $_SERVER['HTTP_USER_AGENT'] ?? null,
            ], [ '%d', '%s', '%s', '%f', '%f', '%f', '%s', '%s', '%s', '%d', '%s', '%s', '%s' ] );

            $tx_id = $wpdb->insert_id;
            $wpdb->query( 'COMMIT' );

            Pilah_Usermeta_Sync::sync_from_db( $user_id );
            Pilah_Security::write_audit_log( $user_id, 'credit_point', 'transaction', $tx_id,
                [ 'balance' => $balance_before ],
                [ 'balance' => $balance_after, 'amount' => $amount, 'tid' => $tid ] );

            return [ 'success' => true, 'message' => 'Point berhasil ditambahkan', 'new_balance' => $balance_after ];

        } catch ( Exception $e ) {
            $wpdb->query( 'ROLLBACK' );
            error_log( '[Pilah] credit_point gagal: ' . $e->getMessage() );
            return [ 'success' => false, 'message' => 'Terjadi kesalahan sistem.' ];
        }
    }

    public static function debit_point_for_withdraw( $user_id ) {
        global $wpdb;
        $user_id = intval( $user_id );
        $amount  = PILAH_MIN_WITHDRAW; // Selalu 300

        if ( ! Pilah_Security::check_rate_limit( $user_id, 'withdraw', PILAH_RATE_LIMIT_WITHDRAW ) )
            return [ 'success' => false, 'message' => 'Terlalu banyak permintaan withdraw.' ];

        $wpdb->query( 'START TRANSACTION' );
        try {
            $locked_row = $wpdb->get_row( $wpdb->prepare(
                "SELECT * FROM pilah_point WHERE user_id = %d FOR UPDATE", $user_id ) );
            if ( ! $locked_row ) throw new Exception( 'Record point tidak ditemukan' );

            $balance_before = floatval( $locked_row->balance );
            if ( $balance_before < $amount ) {
                $wpdb->query( 'ROLLBACK' );
                return [ 'success' => false, 'message' => sprintf(
                    'Point tidak mencukupi. Point Anda: %s. Dibutuhkan: %s.',
                    number_format( $balance_before, 0 ), number_format( $amount, 0 ) ) ];
            }

            $balance_after = $balance_before - $amount;
            $new_version   = intval( $locked_row->version ) + 1;

            $wpdb->query( $wpdb->prepare(
                "UPDATE pilah_point SET balance = %f, version = %d WHERE user_id = %d AND version = %d",
                $balance_after, $new_version, $user_id, intval( $locked_row->version ) ) );

            $wpdb->insert( 'pilah_transaction', [
                'user_id'        => $user_id,
                'type'           => 'debit',
                'category'       => 'withdraw',
                'amount'         => $amount,
                'balance_before' => $balance_before,
                'balance_after'  => $balance_after,
                'status'         => 'pending',
                'ip_address'     => Pilah_Security::get_client_ip(),
                'user_agent'     => $_SERVER['HTTP_USER_AGENT'] ?? null,
            ], [ '%d', '%s', '%s', '%f', '%f', '%f', '%s', '%s', '%s' ] );

            $tx_id          = $wpdb->insert_id;
            $voucher_result = Pilah_Voucher::generate( $user_id, $tx_id, $amount );
            if ( ! $voucher_result['success'] )
                throw new Exception( 'Gagal generate voucher: ' . $voucher_result['message'] );

            $wpdb->query( $wpdb->prepare(
                "UPDATE pilah_transaction SET status = 'completed', ref_voucher_id = %d WHERE id = %d",
                $voucher_result['voucher_id'], $tx_id ) );

            $wpdb->query( 'COMMIT' );

            Pilah_Usermeta_Sync::sync_from_db( $user_id );
            Pilah_Security::write_audit_log( $user_id, 'withdraw_point', 'transaction', $tx_id,
                [ 'balance' => $balance_before ],
                [ 'balance' => $balance_after, 'voucher_code' => $voucher_result['code'] ] );

            return [
                'success'      => true,
                'message'      => 'Withdraw berhasil!',
                'voucher_code' => $voucher_result['code'],
                'new_balance'  => $balance_after,
            ];

        } catch ( Exception $e ) {
            $wpdb->query( 'ROLLBACK' );
            error_log( '[Pilah] debit_for_withdraw gagal: ' . $e->getMessage() );
            return [ 'success' => false, 'message' => 'Terjadi kesalahan. Point tidak dikurangi.' ];
        }
    }
}
