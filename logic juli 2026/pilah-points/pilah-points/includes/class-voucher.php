<?php
if ( ! defined( 'ABSPATH' ) ) exit;

class Pilah_Voucher {

    // Huruf O dan I dihapus untuk menghindari kebingungan dengan 0 dan 1
    const CHARSET     = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    const CODE_LENGTH = 8;
    const MAX_RETRY   = 10;

    public static function generate( $user_id, $tx_id, $point_value ) {
        global $wpdb;
        $code = null;
        $attempt = 0;

        while ( $attempt < self::MAX_RETRY ) {
            $candidate = self::generate_code();
            $exists = $wpdb->get_var( $wpdb->prepare(
                "SELECT COUNT(*) FROM pilah_voucher WHERE code = %s", $candidate ) );
            if ( intval( $exists ) === 0 ) {
                $code = $candidate;
                break;
            }
            $attempt++;
        }

        if ( ! $code ) return [ 'success' => false, 'message' => 'Gagal generate kode unik' ];

        $inserted = $wpdb->insert( 'pilah_voucher', [
            'user_id'        => intval( $user_id ),
            'transaction_id' => intval( $tx_id ),
            'code'           => $code,
            'point_value'    => floatval( $point_value ),
            'status'         => 'active',
        ], [ '%d', '%d', '%s', '%f', '%s' ] );

        if ( false === $inserted ) return [ 'success' => false, 'message' => 'Gagal menyimpan voucher' ];

        return [ 'success' => true, 'code' => $code, 'voucher_id' => $wpdb->insert_id ];
    }

    private static function generate_code() {
        $charset = self::CHARSET;
        $len     = strlen( $charset );
        $code    = '';
        for ( $i = 0; $i < self::CODE_LENGTH; $i++ ) {
            $code .= $charset[ random_int( 0, $len - 1 ) ];
        }
        return $code;
    }

    public static function validate( $code ) {
        global $wpdb;
        $code    = strtoupper( sanitize_text_field( $code ) );
        $voucher = $wpdb->get_row( $wpdb->prepare(
            "SELECT * FROM pilah_voucher WHERE code = %s LIMIT 1", $code ) );

        if ( ! $voucher ) return [ 'valid' => false, 'message' => 'Kode voucher tidak ditemukan' ];

        if ( $voucher->status !== 'active' ) {
            $msg = match( $voucher->status ) {
                'used'      => 'Voucher sudah pernah digunakan',
                'cancelled' => 'Voucher telah dibatalkan',
                'flagged'   => 'Voucher sedang dalam peninjauan',
                default     => 'Voucher tidak valid',
            };
            return [ 'valid' => false, 'voucher' => $voucher, 'message' => $msg ];
        }

        return [ 'valid' => true, 'voucher' => $voucher, 'message' => 'Voucher valid' ];
    }

    public static function mark_as_used( $code, $used_by = null ) {
        global $wpdb;
        $validate = self::validate( $code );
        if ( ! $validate['valid'] ) return [ 'success' => false, 'message' => $validate['message'] ];

        $updated = $wpdb->query( $wpdb->prepare(
            "UPDATE pilah_voucher SET status = 'used', used_at = NOW() WHERE code = %s AND status = 'active'",
            $code ) );

        if ( ! $updated ) return [ 'success' => false, 'message' => 'Gagal update status voucher' ];

        Pilah_Security::write_audit_log(
            $validate['voucher']->user_id, 'voucher_used', 'voucher',
            $validate['voucher']->id,
            [ 'status' => 'active' ],
            [ 'status' => 'used', 'used_by' => $used_by ]
        );

        return [ 'success' => true, 'message' => 'Voucher berhasil digunakan' ];
    }
}
