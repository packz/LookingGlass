$('#passphrase').keypress(function(e){
  if (e.which == 13) {
    $('.message-locked').fadeOut();
    $('#passphrase-modal').modal('hide');
    passphrase_submitted();
  };
});

$('#show-pass').click(function() {
  if ($(this).is(':checked')) {
    $('#passphrase').attr('type', 'text');
  } else {
    $('#passphrase').attr('type', 'password');
  };
});

$(document).ready(function(){
  $('#passphrase-modal').on('shown.bs.modal', function () {
    $('#passphrase').val('');
    $('#passphrase').focus();
  });
});
