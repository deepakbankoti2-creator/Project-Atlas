<?php
defined('BASEPATH') OR exit('No direct script access allowed');

$route['default_controller'] = 'chat';
$route['404_override'] = '';
$route['translate_uri_dashes'] = FALSE;

$route['chat'] = 'chat/index';
$route['chat/ask'] = 'chat/ask';
$route['chat/feedback'] = 'chat/feedback';
$route['chat/escalations'] = 'chat/escalations';
$route['chat/switch_client/(:any)'] = 'chat/switch_client/$1';
