var fs = require('fs');
var path = require('path');

var openpgp = require('openpgp');

var pages = require('./pages.js');
var utils = require('./utils.js');

// File types left to test:
// docx, doc, ppt, mp4, mp3, wav, html, zip
describe('Submission file process', function() {
  var filenames = fs.readdirSync(utils.vars.testFileDir);
  var dirs = filenames.map(utils.makeTestFilePath);

  var chksums = {};

  for (var i = 0; i < dirs.length; i++) {
    var s = fs.readFileSync(dirs[i]);
    var c = utils.checksum(s);
    chksums[filenames[i]] = c;
  }

  beforeEach(function() {
    filenames.forEach(function(t) {
      try {
        fs.unlinkSync(path.join(browser.params.tmpDir, t));
      } catch (e) {
        /* eslint-disable no-console */
        console.error(e);
        /* eslint-enable no-console */
      }
    });
  });

  function uploadAndDownloadTest() {
    var wb = new pages.whistleblower();
    var rec = new pages.receiver();
    
    wb.performSubmission('Test file consistency').then(function(receipt) {
      wb.viewReceipt(receipt);
      
      // Add each file as an attachment.
      dirs.forEach(function(name) {
        wb.submitFile(name); 
      });

      utils.logout();
      
      // Login as the receiver
      utils.login_receiver('Recipient2', utils.vars['user_password']);
      rec.viewMostRecentSubmission();

      // Download each file
      element.all(by.cssContainingText("button", "download")).each(function(btn, i) {
        btn.click();
        browser.waitForAngular();

        var name = filenames[i];
        var fullpath = path.resolve(path.join(browser.params.tmpDir, name));
        utils.waitForFile(fullpath, 2000).then(function() {
          // Check that each downloaded file's checksum matches its original
          var test = utils.checksum(fs.readFileSync(fullpath));
          expect(test).toEqual(chksums[name]);
        });
      });

    });
  }

  function uploadAndDecryptTest() {
    var wb = new pages.whistleblower();
    var rec = new pages.receiver();
    
    var opts = { encoding: 'utf8', flag: 'r' };
    var priv_key = fs.readFileSync('../backend/globaleaks/tests/keys/VALID_PGP_KEY1_PRV', opts);
    var pub_key = fs.readFileSync('../backend/globaleaks/tests/keys/VALID_PGP_KEY1_PUB', opts);

    wb.performSubmission('Test file openpgp consistency').then(function(receipt) {
      // attach files to submission
      wb.viewReceipt(receipt);
      
      dirs.forEach(function(name) {
        wb.submitFile(name); 
      });

      utils.logout();
      
      utils.login_receiver('Recipient1', utils.vars['user_password']);
      rec.viewMostRecentSubmission();

      element.all(by.cssContainingText("button", "download")).each(function(btn, i) {
        btn.click();
        browser.waitForAngular();

        var name = filenames[i];
        var fullpath = path.resolve(path.join(browser.params.tmpDir, name + '.pgp'));
        utils.waitForFile(fullpath, 2000).then(function() {
          var data = fs.readFileSync(fullpath, opts);

          var options = {
            message: openpgp.message.readArmored(data),
            publicKeys: pub_key,
            privateKey: priv_key,
          };

          openpgp.decrypt(options).then(function(result) {
            expect(result.valid).toBeTrue();

            // check the files to see if they match
            var test = utils.checksum(result.data);
            expect(test).toEqual(chksums[name]);
          });
        });
      });
    });
  }

  if (browser.params.verifyFileDownload) {
    it('uploaded and downloaded plaintext files should match', uploadAndDownloadTest);
    it('uploaded and encrypted files should match downloaded and decrypted files', uploadAndDecryptTest);
  }
});
