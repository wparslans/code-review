<?php
/*
Plugin Name: Bad Plugin Example
Description: A test plugin with bad practices for AI Reviewer + PHPCS.
Version: 1.0
Author: Someone
*/

global $wpdb;
$results = $wpdb->get_results("SELECT * FROM {$wpdb->prefix}users WHERE user_login = '" . $_GET['user'] . "'");

if ( isset($_POST['my_form_submit']) ) {
    update_option('my_plugin_option', $_POST['my_input']);
}

echo '<h1>' . $_GET['title'] . '</h1>';

function BadFunctionNAME($Param) {
    echo "Bad style! " . $Param;
}
add_action('init', 'BadFunctionNAME');
